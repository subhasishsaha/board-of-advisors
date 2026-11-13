"""
Board of Advisors - Autonomous Multi-Agent Decision Council
Powered by Gemini 3.8 Flash via Antigravity CLI detached execution.
"""

from board.config import AGY_EXECUTABLE, DEFAULT_MODEL, DEFAULT_EFFORT
from board.advisor import Advisor
from board.orchestrator import BoardOrchestrator, BoardMessage
from board.invoker import AntigravityInvoker
from board.memory import AdvisorMemory

__all__ = [
    "AGY_EXECUTABLE",
    "DEFAULT_MODEL",
    "DEFAULT_EFFORT",
    "Advisor",
    "BoardOrchestrator",
    "BoardMessage",
    "AntigravityInvoker",
    "AdvisorMemory",
]
