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
    """Find the path to the agy (Antigravity CLI) executable, preventing CWD / repo hijacking."""
    env_path = os.environ.get("AGY_PATH")
    if env_path:
        try:
            p = Path(env_path).resolve()
            if p.is_file():
                return str(p)
        except Exception:
            return env_path
    
    proj_root = PROJECT_ROOT.resolve()
    try:
        cwd = Path.cwd().resolve()
    except Exception:
        cwd = proj_root

    try:
        which_path = shutil.which("agy")
        if which_path and os.path.isfile(which_path):
            which_res = Path(which_path).resolve()
            # Prevent local CWD / repo executable hijacking (CWE-426)
            is_in_proj = False
            try:
                is_in_proj = which_res.is_relative_to(proj_root) or which_res.is_relative_to(cwd)
            except (ValueError, AttributeError):
                pass
            if not is_in_proj:
                return str(which_res)
    except Exception:
        pass

    # Common Windows install path
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidate = (Path(local_app_data) / "agy" / "bin" / "agy.exe").resolve()
        try:
            if candidate.is_file():
                return str(candidate)
        except PermissionError:
            # File exists but access to stat is restricted in sandbox
            return str(candidate)
        except Exception:
            pass

    # User profile fallback
    user_profile = os.environ.get("USERPROFILE", "")
    if user_profile:
        candidate = (Path(user_profile) / "AppData" / "Local" / "agy" / "bin" / "agy.exe").resolve()
        try:
            if candidate.is_file():
                return str(candidate)
        except PermissionError:
            return str(candidate)
        except Exception:
            pass

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
