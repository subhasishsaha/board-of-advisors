import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import yaml

from board.advisor import Advisor
from board.config import DEFAULT_ADVISORS_CONFIG, DEFAULT_DISCUSSION_ROUNDS, SESSIONS_DIR
from board.invoker import AntigravityInvoker

logger = logging.getLogger(__name__)

class BoardMessage:
    def __init__(self, sender: str, tag: str, content: str, stage: str):
        self.sender = sender
        self.tag = tag
        self.content = content
        self.stage = stage
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sender": self.sender,
            "tag": self.tag,
            "content": self.content,
            "stage": self.stage,
            "timestamp": self.timestamp.isoformat(),
        }

class BoardOrchestrator:
    """
    Coordinates the multi-agent chat debate between autonomous board members,
    handles @mention parsing and targeted question routing, and synthesizes
    the final Plan of Action.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        discussion_rounds: int = DEFAULT_DISCUSSION_ROUNDS,
        on_message_callback: Optional[Callable[[BoardMessage], None]] = None,
    ):
        self.config_path = config_path or DEFAULT_ADVISORS_CONFIG
        self.discussion_rounds = discussion_rounds
        self.on_message_callback = on_message_callback

        self.advisors: List[Advisor] = []
        self.advisors_by_tag: Dict[str, Advisor] = {}
        self.advisors_by_id: Dict[str, Advisor] = {}
        self.messages: List[BoardMessage] = []
        self.current_problem: str = ""
        self.final_plan: str = ""

        self.synthesizer_invoker = AntigravityInvoker()
        self._load_advisors()

    def _load_advisors(self) -> None:
        """Load advisor profiles and initialize instances."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Advisors config not found at: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        advisor_defs = data.get("advisors", [])
        for a_def in advisor_defs:
            adv = Advisor(
                advisor_id=a_def["id"],
                name=a_def["name"],
                tag=a_def["tag"],
                role=a_def["role"],
                persona=a_def["persona"],
                bio=a_def.get("bio", ""),
                avatar=a_def.get("avatar", "👤"),
                color=a_def.get("color", "white"),
                core_beliefs=a_def.get("core_beliefs", []),
            )
            self.advisors.append(adv)
            self.advisors_by_tag[adv.tag.lower()] = adv
            self.advisors_by_id[adv.id] = adv

    def _record_message(self, sender: str, tag: str, content: str, stage: str) -> BoardMessage:
        msg = BoardMessage(sender, tag, content, stage)
        self.messages.append(msg)
        if self.on_message_callback:
            self.on_message_callback(msg)
        return msg

    def format_transcript(self, last_n: Optional[int] = None) -> str:
        """Format the chronological discussion into readable text for prompt context."""
        selected = self.messages if last_n is None else self.messages[-last_n:]
        lines = []
        for m in selected:
            lines.append(f"[{m.sender} ({m.tag})]:\n{m.content}\n")
        return "\n".join(lines)

    def extract_mentions(self, text: str) -> List[str]:
        """Find all @Advisor tags mentioned in the text."""
        mentions = []
        # Find words starting with @
        found = re.findall(r"@\w+", text)
        for tag in found:
            clean_tag = tag.lower()
            if clean_tag in self.advisors_by_tag:
                mentions.append(self.advisors_by_tag[clean_tag].tag)
        return list(dict.fromkeys(mentions))  # deduplicate preserving order

    async def run_deliberation(self, problem: str, user_context: str = "") -> str:
        """
        Execute the full Board of Advisors deliberation pipeline:
        1. Opening statements from all advisors (concurrent/detached).
        2. Discussion & debate rounds routing targeted @mentions.
        3. Comprehensive action plan synthesis.
        4. Memory updates.
        """
        self.current_problem = problem
        self.messages.clear()

        # Step 0: Record the user problem
        self._record_message("USER", "@User", problem, stage="problem")

        # Step 1: Initial Round (Opening Perspectives)
        # We can invoke advisors in parallel via detached agy
        async def fetch_initial(advisor: Advisor):
            response = await advisor.generate_initial_assessment(
                problem=problem,
                all_advisors=self.advisors,
                user_notes=user_context,
            )
            return advisor, response

        initial_tasks = [fetch_initial(a) for a in self.advisors]
        initial_results = await asyncio.gather(*initial_tasks, return_exceptions=True)

        # Record initial assessments
        pending_questions: Dict[str, List[str]] = {a.tag: [] for a in self.advisors}
        for res in initial_results:
            if isinstance(res, Exception):
                logger.error(f"Error in initial assessment: {res}")
                continue
            advisor, response = res
            self._record_message(advisor.name, advisor.tag, response, stage="initial_assessment")

            # Check for tags in the response
            tags = self.extract_mentions(response)
            for t in tags:
                pending_questions[t].append(f"From {advisor.name} ({advisor.tag}): {response[:150]}...")

        # Step 2: Discussion Rounds
        for round_idx in range(1, self.discussion_rounds + 1):
            stage_name = f"debate_round_{round_idx}"

            # In debate round, we give priority to advisors who were tagged
            # Order advisors: tagged ones first, then others
            tagged_order = sorted(
                self.advisors,
                key=lambda a: len(pending_questions.get(a.tag, [])),
                reverse=True
            )

            for advisor in tagged_order:
                direct_qs = pending_questions.get(advisor.tag, [])
                transcript_text = self.format_transcript()

                try:
                    response = await advisor.generate_discussion_turn(
                        problem=problem,
                        transcript_so_far=transcript_text,
                        all_advisors=self.advisors,
                        targeted_questions=direct_qs if direct_qs else None,
                    )
                    self._record_message(advisor.name, advisor.tag, response, stage=stage_name)

                    # Clear handled questions
                    pending_questions[advisor.tag] = []

                    # Extract new tags from this response for the next turn
                    new_tags = self.extract_mentions(response)
                    for t in new_tags:
                        if t != advisor.tag:
                            pending_questions[t].append(f"From {advisor.name} in Round {round_idx}: {response[:150]}...")

                except Exception as e:
                    logger.error(f"Error in debate turn for {advisor.name}: {e}")

        # Step 3: Action Plan Synthesis
        self.final_plan = await self._synthesize_action_plan(problem)
        self._record_message("CHAIR / SYNTHESIS", "@Plan", self.final_plan, stage="action_plan")

        # Step 4: Persist Memories
        self._save_session_memories(problem, self.final_plan)

        return self.final_plan

    async def handle_user_followup(self, user_message: str) -> str:
        """
        Allows the user to ask a follow-up question, challenge an advisor,
        or request plan revisions.
        """
        self._record_message("USER", "@User", user_message, stage="followup_query")
        transcript_text = self.format_transcript()

        # Determine which advisors should answer
        tagged = self.extract_mentions(user_message)
        responding_advisors = []
        if tagged:
            for t in tagged:
                adv = self.advisors_by_tag.get(t.lower())
                if adv:
                    responding_advisors.append(adv)
        else:
            # If no one specifically tagged, pick the 2 most relevant or first two
            responding_advisors = self.advisors[:2]

        responses = []
        for adv in responding_advisors:
            try:
                resp = await adv.generate_discussion_turn(
                    problem=self.current_problem,
                    transcript_so_far=transcript_text,
                    all_advisors=self.advisors,
                    targeted_questions=[f"The User asks: {user_message}"],
                )
                self._record_message(adv.name, adv.tag, resp, stage="followup_response")
                responses.append(f"[{adv.name} ({adv.tag})]:\n{resp}")
            except Exception as e:
                logger.error(f"Error in follow-up for {adv.name}: {e}")

        return "\n\n".join(responses)

    async def _synthesize_action_plan(self, problem: str) -> str:
        """
        Consolidates the entire multi-agent deliberation into a structured,
        high-impact Plan of Action.
        """
        transcript_text = self.format_transcript()

        prompt = f"""You are the Executive Synthesizer and Board Secretary.
The Board of Advisors has just completed an in-depth deliberation regarding this problem:
"{problem}"

=== FULL BOARD DELIBERATION TRANSCRIPT ===
{transcript_text}

=== ASSIGNMENT ===
Synthesize the advisors' deliberation into a decisive, authoritative, and structured PLAN OF ACTION for the user.

Your Plan of Action must contain the following markdown sections:

# 📋 BOARD OF ADVISORS: CONSOLIDATED PLAN OF ACTION

### 1. Executive Verdict & Strategic Stance
- Clear, unambiguous recommendation (Go / No-Go / Conditional Go).
- Core thesis: Why this choice over the alternatives?

### 2. Key Insights & Debates
- The primary consensus points across the board.
- Where advisors clashed (e.g. Elena vs. Marcus or Aris) and how that trade-off is resolved.

### 3. Immediate Action Plan (Weeks 1 - 2)
- Specific, high-priority tasks to execute right now.
- Owners/mindset for each task.

### 4. Milestones & Validation Gates (Days 30, 60, 90)
- Concrete success criteria and kill-switches / pivot criteria.

### 5. Risk Matrix & Mitigations
- Financial / Runway risk mitigation (addressing @Marcus's concerns).
- Market / Adoption risk mitigation (addressing @Elena's concerns).
- Technical / Architecture risk mitigation (addressing @Aris's concerns).
- Governance / Human / Legal safeguards (addressing @Maya's concerns).

### 6. Advisor Closing Verdicts
- A 1-sentence bottom-line takeaway attributed to each advisor (@Elena, @Marcus, @Aris, @Maya).

Make the plan actionable, pragmatic, and inspiringly clear."""

        return await self.synthesizer_invoker.invoke_async(prompt)

    def _save_session_memories(self, problem: str, plan: str) -> None:
        """Update each advisor's long-term memory with the outcome of this session."""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        for adv in self.advisors:
            # Extract this advisor's messages
            adv_msgs = [m.content for m in self.messages if m.tag == adv.tag]
            adv_stance = adv_msgs[0] if adv_msgs else "No initial stance recorded"
            adv.memory.record_decision(
                problem=problem,
                recommendation=adv_stance[:250],
                consensus_plan=plan[:300],
            )
            adv.memory.clear_working_notes()

        # Save session transcript to storage/sessions/
        session_file = SESSIONS_DIR / f"session_{session_id}.json"
        try:
            with open(session_file, "w", encoding="utf-8") as f:
                import json
                json.dump({
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "problem": problem,
                    "messages": [m.to_dict() for m in self.messages],
                    "final_plan": plan,
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save session log: {e}")
