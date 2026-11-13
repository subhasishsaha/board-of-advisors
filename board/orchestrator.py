import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import yaml

from board.advisor import Advisor
from board.advisor_builder import parse_advisors_json
from board.config import DEFAULT_ADVISORS_CONFIG, SESSIONS_DIR
from board.invoker import AntigravityInvoker

logger = logging.getLogger(__name__)

MAX_ROUNDS = 3

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
    supports dynamic generation of problem-tailored advisors (up to 10),
    handles @mention parsing, targeted question routing, flexible rounds (at most 3),
    and synthesizes the final Plan of Action.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        max_rounds: int = MAX_ROUNDS,
        on_message_callback: Optional[Callable[[BoardMessage], None]] = None,
        user_input_callback: Optional[Callable[[Advisor, str], Any]] = None,
    ):
        self.config_path = config_path or DEFAULT_ADVISORS_CONFIG
        self.max_rounds = max_rounds
        self.on_message_callback = on_message_callback
        self.user_input_callback = user_input_callback

        self.advisors: List[Advisor] = []
        self.advisors_by_tag: Dict[str, Advisor] = {}
        self.advisors_by_id: Dict[str, Advisor] = {}
        self.messages: List[BoardMessage] = []
        self.current_problem: str = ""
        self.final_plan: str = ""

        self.synthesizer_invoker = AntigravityInvoker()

    def _load_predefined_advisors(self) -> None:
        """Fallback to load default predefined advisors from YAML config."""
        if not self.config_path.exists():
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        advisor_defs = data.get("advisors", [])
        self._register_advisor_defs(advisor_defs)

    def _register_advisor_defs(self, advisor_defs: List[Dict[str, Any]]) -> None:
        """Register a list of advisor definitions into the orchestrator."""
        self.advisors = []
        self.advisors_by_tag = {}
        self.advisors_by_id = {}

        for a_def in advisor_defs[:10]:  # Cap at 10 advisors
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

    async def build_dynamic_advisors(self, problem: str) -> List[Advisor]:
        """
        Dynamically synthesize a bespoke board of at most 10 advisors tailored
        specifically to the user's decision dilemma.
        """
        prompt = f"""You are the Master Executive Search Architect and Corporate Governance Lead.
The user is facing this strategic decision problem:
"{problem}"

=== OBJECTIVE ===
Assemble a bespoke, world-class Board of Advisors specifically tailored to evaluate and resolve this exact dilemma.
Select between 3 and 10 distinct advisors (at most 10). Choose the optimal number based on the multifaceted nature of the challenge (typically 4 to 6).

Requirements for each advisor:
1. Diversity of Thought: Include opposing forces (e.g. aggressive growth, downside risk, technical feasibility, legal/compliance, customer value, operational execution).
2. Domain Relevance: Their functional expertise must directly address key risks and opportunities in the user's dilemma.
3. Realistic & Vivid Personas: Give them distinct cognitive biases, tones, and professional philosophies so they challenge each other authentically.
4. Unique @Tags: Give each an @Tag (e.g., @Rachel, @David, @Marcus, @Elena) so colleagues can tag them directly.

Output ONLY a valid JSON array of advisor objects with these exact keys:
[
  {{
    "id": "short_unique_id",
    "name": "Full Name",
    "tag": "@UniqueTag",
    "role": "Executive Title & Domain",
    "avatar": "Single Emoji (e.g. 🎯, 📊, ⚡, ⚖️, 🛡️, 🚀, 💡)",
    "color": "Rich color name (e.g. bright_magenta, bright_cyan, bright_green, bright_yellow, bright_blue, gold1, plum2, turquoise2)",
    "bio": "1-2 sentence background",
    "persona": "Detailed persona instructions describing how they think, what they scrutinize, how they debate, and their communication style",
    "core_beliefs": ["Core principle 1", "Core principle 2"]
  }}
]
"""
        try:
            raw_response = await self.synthesizer_invoker.invoke_async(prompt)
            advisor_defs = parse_advisors_json(raw_response)
            if not advisor_defs:
                raise ValueError("Parsed advisor list is empty")
            self._register_advisor_defs(advisor_defs)
            return self.advisors
        except Exception as e:
            logger.error(f"Dynamic advisor generation failed ({e}), falling back to predefined advisors")
            self._load_predefined_advisors()
            return self.advisors

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
        found = re.findall(r"@\w+", text)
        for tag in found:
            clean_tag = tag.lower()
            if clean_tag in self.advisors_by_tag:
                mentions.append(self.advisors_by_tag[clean_tag].tag)
        return list(dict.fromkeys(mentions))

    def check_user_mention(self, text: str) -> Optional[str]:
        """
        Check if the text contains a direct tag or question addressed to the user (@User).
        Returns the extracted question/inquiry or None.
        """
        if not re.search(r"@user\b", text, re.IGNORECASE):
            return None

        # Extract sentences containing @User
        sentences = re.split(r"(?<=[.?!])\s+", text)
        matched = [s.strip() for s in sentences if re.search(r"@user\b", s, re.IGNORECASE)]
        if matched:
            return " ".join(matched)
        return text.strip()

    async def _request_user_input(self, advisor: Advisor, question: str) -> Optional[str]:
        """Invoke the callback to suspend round table and get user input."""
        if not self.user_input_callback:
            return None
        try:
            res = self.user_input_callback(advisor, question)
            if asyncio.iscoroutine(res):
                return await res
            return res
        except Exception as e:
            logger.error(f"Error obtaining user input: {e}")
            return None

    async def _check_if_consensus_reached(self, problem: str) -> bool:
        """
        Check if the board has reached substantial alignment and can conclude
        before the maximum round limit.
        """
        transcript_text = self.format_transcript(last_n=12)
        prompt = f"""You are the Board Secretary. Read the recent debate between the advisors:
Problem: "{problem}"

Recent Discussion:
{transcript_text}

Question: Have the advisors reached substantial consensus or a clear unified direction where further debate is unnecessary?
Reply with ONLY 'YES' if consensus is reached, or 'NO' if there are still active disputes, direct questions to answer, or stark disagreements."""

        try:
            resp = await self.synthesizer_invoker.invoke_async(prompt)
            return "YES" in resp.strip().upper()
        except Exception:
            return False

    async def run_deliberation(self, problem: str, user_context: str = "") -> str:
        """
        Execute the full Board of Advisors deliberation pipeline:
        1. Dynamically build tailored advisors if not already configured.
        2. Opening statements from all advisors (concurrent/detached).
        3. Flexible discussion rounds (at most 3 rounds).
           On round 3 (the last round), explicitly mandate that advisors come to a conclusion.
        4. Comprehensive action plan synthesis.
        5. Memory persistence.
        """
        self.current_problem = problem
        self.messages.clear()

        # Build dynamic advisors if not already generated
        if not self.advisors:
            await self.build_dynamic_advisors(problem)

        # Record the user problem
        self._record_message("USER", "@User", problem, stage="problem")

        # Step 1: Round 1 - Opening Perspectives
        async def fetch_initial(advisor: Advisor):
            response = await advisor.generate_initial_assessment(
                problem=problem,
                all_advisors=self.advisors,
                user_notes=user_context,
            )
            return advisor, response

        initial_tasks = [fetch_initial(a) for a in self.advisors]
        initial_results = await asyncio.gather(*initial_tasks, return_exceptions=True)

        pending_questions: Dict[str, List[str]] = {a.tag: [] for a in self.advisors}
        for res in initial_results:
            if isinstance(res, Exception):
                logger.error(f"Error in initial assessment: {res}")
                continue
            advisor, response = res
            self._record_message(advisor.name, advisor.tag, response, stage="round_1_opening")

            # Extract tags from response
            tags = self.extract_mentions(response)
            for t in tags:
                pending_questions[t].append(f"From {advisor.name} ({advisor.tag}): {response[:150]}...")

        # If any opening assessment asked @User for critical input, suspend and collect it
        for res in initial_results:
            if isinstance(res, Exception):
                continue
            advisor, response = res
            user_q = self.check_user_mention(response)
            if user_q and self.user_input_callback:
                user_ans = await self._request_user_input(advisor, user_q)
                if user_ans and user_ans.strip():
                    self._record_message("USER", "@User", user_ans.strip(), stage="round_1_user_input")
                    advisor.memory.add_working_note(f"User clarified: {user_ans[:80]}")

        # Step 2: Flexible Discussion Rounds (Up to MAX_ROUNDS = 3)
        current_round = 2
        while current_round <= self.max_rounds:
            is_final = (current_round == self.max_rounds)

            # Check if consensus was already reached before round 3
            if current_round == 3:
                # Force final round mandate on round 3
                is_final = True

            stage_name = f"round_{current_round}_final" if is_final else f"round_{current_round}_debate"

            # Sort advisors: those tagged with direct questions speak first
            speaking_order = sorted(
                self.advisors,
                key=lambda a: len(pending_questions.get(a.tag, [])),
                reverse=True
            )

            for advisor in speaking_order:
                direct_qs = pending_questions.get(advisor.tag, [])
                transcript_text = self.format_transcript()

                try:
                    response = await advisor.generate_discussion_turn(
                        problem=problem,
                        transcript_so_far=transcript_text,
                        all_advisors=self.advisors,
                        targeted_questions=direct_qs if direct_qs else None,
                        is_final_round=is_final,
                    )
                    self._record_message(advisor.name, advisor.tag, response, stage=stage_name)

                    # Clear handled questions
                    pending_questions[advisor.tag] = []

                    # If advisor tagged @User for input, suspend deliberation and wait for user's response
                    user_q = self.check_user_mention(response)
                    if user_q and self.user_input_callback:
                        user_ans = await self._request_user_input(advisor, user_q)
                        if user_ans and user_ans.strip():
                            self._record_message(
                                "USER",
                                "@User",
                                user_ans.strip(),
                                stage=f"{stage_name}_user_input",
                            )
                            advisor.memory.add_working_note(f"User clarified: {user_ans[:80]}")

                    # If not final round, extract new tags for subsequent turn
                    if not is_final:
                        new_tags = self.extract_mentions(response)
                        for t in new_tags:
                            if t != advisor.tag:
                                pending_questions[t].append(f"From {advisor.name} in Round {current_round}: {response[:150]}...")

                except Exception as e:
                    logger.error(f"Error in debate turn for {advisor.name}: {e}")

            # If this was already marked final, stop here
            if is_final:
                break

            # If this was round 2, check if consensus reached early
            if current_round == 2:
                # Check if there are virtually no pending questions and consensus is reached
                has_pending = any(len(qs) > 0 for qs in pending_questions.values())
                if not has_pending and await self._check_if_consensus_reached(problem):
                    # Consensus achieved in round 2!
                    break

            current_round += 1

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
                    is_final_round=False,
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
        advisors_summary = ", ".join([f"{a.name} ({a.tag})" for a in self.advisors])

        prompt = f"""You are the Executive Synthesizer and Board Secretary.
The Board of Advisors ({advisors_summary}) has just completed their final deliberation regarding this problem:
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
- Where advisors clashed and how the conflict was resolved in the final round.

### 3. Immediate Action Plan (Weeks 1 - 2)
- Specific, high-priority tasks to execute right now.
- Mindset and primary considerations for each task.

### 4. Milestones & Validation Gates (Days 30, 60, 90)
- Concrete success criteria and kill-switches / pivot criteria.

### 5. Risk Matrix & Mitigations
- Key domain risks raised during the debate and their mitigations.

### 6. Advisor Closing Verdicts
- A 1-sentence bottom-line takeaway attributed to each board advisor.

Make the plan actionable, pragmatic, and inspiringly clear."""

        return await self.synthesizer_invoker.invoke_async(prompt)

    def _save_session_memories(self, problem: str, plan: str) -> None:
        """Update each advisor's long-term memory with the outcome of this session."""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        for adv in self.advisors:
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
