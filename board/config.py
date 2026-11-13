import os
import shutil
from pathlib import Path

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = PROJECT_ROOT / "storage"
MEMORY_DIR = STORAGE_DIR / "memory"
SESSIONS_DIR = STORAGE_DIR / "sessions"
CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_ADVISORS_CONFIG = CONFIG_DIR / "advisors.yaml"

# Ensure directories exist
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# Antigravity CLI discovery
def find_agy_executable() -> str:
    """Find the path to the agy (Antigravity CLI) executable."""
    env_path = os.environ.get("AGY_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    
    which_path = shutil.which("agy")
    if which_path and os.path.isfile(which_path):
        return which_path

    # Common Windows install path
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidate = Path(local_app_data) / "agy" / "bin" / "agy.exe"
        if candidate.is_file():
            return str(candidate)

    # User profile fallback
    user_profile = os.environ.get("USERPROFILE", "")
    if user_profile:
        candidate = Path(user_profile) / "AppData" / "Local" / "agy" / "bin" / "agy.exe"
        if candidate.is_file():
            return str(candidate)

    # Default fallback
    return "agy"

AGY_EXECUTABLE = find_agy_executable()

# Default LLM parameters
DEFAULT_MODEL = os.environ.get("AGY_MODEL", "gemini-3.8-flash-medium")
DEFAULT_EFFORT = os.environ.get("AGY_EFFORT", "medium")
DEFAULT_TIMEOUT = int(os.environ.get("AGY_TIMEOUT", "120"))

# Orchestration parameters
DEFAULT_DISCUSSION_ROUNDS = 2
MAX_ADVISOR_CONCURRENT_CALLS = 3
