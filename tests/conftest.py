import sys
import pytest
from pathlib import Path
import board.config
import board.memory
import board.orchestrator

@pytest.fixture(autouse=True)
def isolate_test_storage(tmp_path, monkeypatch):
    """
    Ensure all tests run with isolated temporary storage directories,
    preventing any test runs from polluting workspace storage/memory or storage/sessions.
    """
    temp_memory = tmp_path / "memory"
    temp_memory.mkdir(parents=True, exist_ok=True)
    temp_sessions = tmp_path / "sessions"
    temp_sessions.mkdir(parents=True, exist_ok=True)

    # Patch board.config
    monkeypatch.setattr(board.config, "MEMORY_DIR", temp_memory)
    monkeypatch.setattr(board.config, "SESSIONS_DIR", temp_sessions)

    # Patch modules importing MEMORY_DIR or SESSIONS_DIR directly
    monkeypatch.setattr(board.memory, "MEMORY_DIR", temp_memory)
    monkeypatch.setattr(board.orchestrator, "SESSIONS_DIR", temp_sessions)
    if hasattr(board.orchestrator, "MEMORY_DIR"):
        monkeypatch.setattr(board.orchestrator, "MEMORY_DIR", temp_memory)

    # Patch all loaded test and CLI modules in sys.modules
    for mod_name in [
        "tests.test_slash_commands",
        "test_slash_commands",
        "tests.test_security",
        "test_security",
        "main",
    ]:
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
            if hasattr(mod, "SESSIONS_DIR"):
                monkeypatch.setattr(mod, "SESSIONS_DIR", temp_sessions)
            if hasattr(mod, "MEMORY_DIR"):
                monkeypatch.setattr(mod, "MEMORY_DIR", temp_memory)

    yield
