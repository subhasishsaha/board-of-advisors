import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from board.config import MEMORY_DIR

logger = logging.getLogger(__name__)

class AdvisorMemory:
    """
    Manages persistent memory and working state for an individual advisor.
    Persists past decisions, core beliefs, peer impressions, and recent interactions.
    """

    def __init__(self, advisor_id: str, advisor_name: str, memory_dir: Optional[Path] = None):
        clean_id = re.sub(r"[^\w-]", "_", str(advisor_id)).strip("_")
        if not clean_id:
            clean_id = "advisor"
        self.advisor_id = clean_id
        self.advisor_name = advisor_name
        self.memory_dir = (memory_dir or MEMORY_DIR).resolve()
        target_file = (self.memory_dir / f"{self.advisor_id}.json").resolve()
        if not target_file.is_relative_to(self.memory_dir):
            raise ValueError(f"Invalid advisor_id resulting in path outside memory dir: '{advisor_id}'")
        self.memory_file = target_file

        self.core_beliefs: List[str] = []
        self.past_decisions: List[Dict[str, Any]] = []
        self.peer_impressions: Dict[str, str] = {}
        self.working_notes: List[str] = []

        self.load()

    def load(self) -> None:
        """Load memory from JSON file if it exists."""
        if not self.memory_file.exists():
            return

        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.core_beliefs = data.get("core_beliefs", [])
                self.past_decisions = data.get("past_decisions", [])
                self.peer_impressions = data.get("peer_impressions", {})
                self.working_notes = data.get("working_notes", [])
        except Exception as e:
            logger.error(f"Error loading memory for {self.advisor_name} from {self.memory_file}: {e}")

    def save(self) -> None:
        """Persist memory to JSON file."""
        try:
            data = {
                "advisor_id": self.advisor_id,
                "advisor_name": self.advisor_name,
                "updated_at": datetime.now().isoformat(),
                "core_beliefs": self.core_beliefs,
                "past_decisions": self.past_decisions,
                "peer_impressions": self.peer_impressions,
                "working_notes": self.working_notes[-20:],  # keep last 20 working notes
            }
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving memory for {self.advisor_name}: {e}")

    def add_belief(self, belief: str) -> None:
        """Add a fundamental principle or belief to the advisor's worldview."""
        if belief not in self.core_beliefs:
            self.core_beliefs.append(belief)
            self.save()

    def record_decision(self, problem: str, recommendation: str, consensus_plan: str) -> None:
        """Record the outcome and recommendation of a completed decision board session."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "problem": problem,
            "recommendation": recommendation,
            "consensus_plan": consensus_plan,
        }
        self.past_decisions.append(record)
        self.save()

    def update_peer_impression(self, peer_name: str, impression: str) -> None:
        """Record or update personal perspective on a peer advisor."""
        self.peer_impressions[peer_name] = impression
        self.save()

    def add_working_note(self, note: str) -> None:
        """Add a temporary working note during ongoing deliberations."""
        self.working_notes.append(f"[{datetime.now().strftime('%H:%M:%S')}] {note}")
        self.save()

    def clear_working_notes(self) -> None:
        """Reset short-term working notes after session completion."""
        self.working_notes = []
        self.save()

    def format_memory_for_prompt(self, max_past_decisions: int = 3) -> str:
        """Format the advisor's long-term memory and impressions into prompt context."""
        parts = []

        if self.core_beliefs:
            parts.append("### Your Core Guiding Principles:")
            for b in self.core_beliefs:
                parts.append(f"- {b}")

        if self.peer_impressions:
            parts.append("\n### Your Impressions of Fellow Board Members:")
            for peer, imp in self.peer_impressions.items():
                parts.append(f"- {peer}: {imp}")

        if self.past_decisions:
            parts.append("\n### Key Past Advice You Have Given:")
            recent = self.past_decisions[-max_past_decisions:]
            for d in recent:
                parts.append(f"- Problem: {d.get('problem', '')[:80]}...")
                parts.append(f"  Your stance: {d.get('recommendation', '')[:120]}...")

        if not parts:
            return "No previous session memories recorded yet."

        return "\n".join(parts)
