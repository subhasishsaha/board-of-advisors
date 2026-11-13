import logging
from typing import Any, Dict, List, Optional
from board.invoker import AntigravityInvoker
from board.memory import AdvisorMemory

logger = logging.getLogger(__name__)

class Advisor:
    """
    Represents an autonomous LLM board member with their own personality,
    characteristic behavior, private memory, and invoker.
    """

    def __init__(
        self,
        advisor_id: str,
        name: str,
        tag: str,
        role: str,
        persona: str,
        bio: str = "",
        avatar: str = "👤",
        color: str = "white",
        core_beliefs: Optional[List[str]] = None,
        invoker: Optional[AntigravityInvoker] = None,
    ):
        self.id = advisor_id
        self.name = name
        self.tag = tag
        self.role = role
        self.persona = persona.strip()
        self.bio = bio.strip()
        self.avatar = avatar
        self.color = color
        self.core_beliefs = core_beliefs or []

        self.memory = AdvisorMemory(advisor_id=self.id, advisor_name=self.name)
        if core_beliefs:
            for b in core_beliefs:
                self.memory.add_belief(b)

        self.invoker = invoker or AntigravityInvoker()

    def _format_board_directory(self, all_advisors: List["Advisor"]) -> str:
        """Format the roster of other board members and their tags."""
        lines = []
        for a in all_advisors:
            if a.id != self.id:
                lines.append(f"- {a.name} ({a.tag}): {a.role}")
        return "\n".join(lines)

    async def generate_initial_assessment(
        self,
        problem: str,
        all_advisors: List["Advisor"],
        user_notes: str = "",
    ) -> str:
        """
        Produce the advisor's initial perspective on the user's problem.
        Encourages tagging other advisors with specific questions.
        """
        directory = self._format_board_directory(all_advisors)
        memory_context = self.memory.format_memory_for_prompt()

        prompt = f"""You are {self.name} ({self.tag}), serving as {self.role} on the user's executive Board of Advisors.

=== YOUR CHARACTERISTIC & PERSONA ===
{self.persona}

=== YOUR PRIVATE MEMORY & WORLDVIEW ===
{memory_context}

=== BOARD MEMBERS YOU CAN TAG ===
You can tag any colleague using their exact @tag (e.g., @Marcus, @Elena, @Aris, @Maya) to ask them targeted questions, challenge their domain assumptions, or request specific estimates.
{directory}

=== USER'S DECISION PROBLEM ===
"{problem}"
{f'Additional Context: {user_notes}' if user_notes else ''}

=== YOUR ASSIGNMENT ===
Provide your initial domain evaluation. As {self.name}:
1. State your sharp, unfiltered perspective on this problem from your area of expertise.
2. Identify the biggest opportunity and the biggest hidden trap you foresee.
3. Propose your initial recommended stance.
4. TAG AT LEAST ONE OR TWO FELLOW ADVISORS using their @tag with a direct, specific question or challenge (e.g., "{all_advisors[1].tag if len(all_advisors)>1 else '@Advisor'}, how would you calculate the downside risk here?").

Keep your response punchy, high-signal, and executive-level (under 250 words). Avoid generic pleasantries or boilerplate intro."""

        response = await self.invoker.invoke_async(prompt)
        self.memory.add_working_note(f"Initial stance: {response[:100]}...")
        return response

    async def generate_discussion_turn(
        self,
        problem: str,
        transcript_so_far: str,
        all_advisors: List["Advisor"],
        targeted_questions: Optional[List[str]] = None,
        is_final_round: bool = False,
    ) -> str:
        """
        Respond during the collaborative debate phase.
        Specifically addresses any direct questions tagged to this advisor.
        If is_final_round is True, mandates reaching a definitive conclusion.
        """
        directory = self._format_board_directory(all_advisors)
        memory_context = self.memory.format_memory_for_prompt()

        questions_text = ""
        if targeted_questions:
            questions_text = "\n=== DIRECT QUESTIONS ADDRESSED TO YOU ==="
            for q in targeted_questions:
                questions_text += f"\n- {q}"

        if is_final_round:
            round_directives = """=== ⚠️ FINAL ROUND MANDATE ===
THIS IS THE FINAL ROUND OF DELIBERATION. You MUST come to a definitive conclusion!
1. Reconcile remaining trade-offs and resolve any outstanding disputes with your fellow board members.
2. State your clear, unambiguous final stance on what the user must do (e.g., Go, No-Go, or specific Conditional Execution).
3. Deliver your final verdict and the single most critical safeguard or execution milestone.
4. Do NOT leave open-ended questions or punt decisions to future rounds; this is the conclusion."""
        else:
            round_directives = """=== YOUR TURN INSTRUCTIONS ===
1. If colleagues tagged you ({self.tag}) or asked you questions above, ANSWER THEM DIRECTLY first with decisive reasoning.
2. Critique, support, or pressure-test the points made by other advisors in the transcript. Don't just agree; sharpen the trade-offs.
3. Suggest a concrete path forward that synthesizes the best ideas while addressing the risks.
4. Feel free to tag another colleague using their exact @tag if you need their input on a specific trade-off."""

        prompt = f"""You are {self.name} ({self.tag}), {self.role}. You are participating in an active, round-table executive debate on the user's board of advisors.

=== YOUR PERSONA & PERSPECTIVE ===
{self.persona}

=== YOUR PRIVATE MEMORY ===
{memory_context}

=== BOARD DIRECTORY (FELLOW ADVISORS) ===
{directory}

=== ORIGINAL DECISION PROBLEM ===
"{problem}"

=== ONGOING BOARD TRANSCRIPT SO FAR ===
{transcript_so_far}
{questions_text}

{round_directives}

Keep your response direct, authentic to your persona, and under 250 words."""

        response = await self.invoker.invoke_async(prompt)
        self.memory.add_working_note(f"Discussion contribution: {response[:100]}...")
        return response

    async def generate_final_takeaway(
        self,
        problem: str,
        transcript_so_far: str,
    ) -> str:
        """Provide a concise 2-sentence closing recommendation."""
        prompt = f"""You are {self.name} ({self.tag}), {self.role}.
The board debate regarding the following decision has concluded:
Problem: "{problem}"

Transcript highlights:
{transcript_so_far[-1200:]}

In 2-3 sentences max:
Give your final, definitive verdict and the single most critical condition or milestone the user must meet for this plan to succeed. Be concise and authoritative."""

        response = await self.invoker.invoke_async(prompt)
        return response
