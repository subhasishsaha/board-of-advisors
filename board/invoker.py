import asyncio
import logging
import os
import subprocess
import time
from typing import Optional, Tuple
from board.config import AGY_EXECUTABLE, DEFAULT_MODEL, DEFAULT_EFFORT, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

# Windows Process Flags for Detached Mode
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008

class AntigravityInvoker:
    """
    Invokes the Antigravity CLI ('agy') in detached mode to run LLM reasoning
    using Gemini 3.8 Flash with medium effort.
    """

    def __init__(
        self,
        executable_path: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        effort: str = DEFAULT_EFFORT,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.executable_path = executable_path or AGY_EXECUTABLE
        self.model = model
        self.effort = effort
        self.timeout = timeout

    def build_command(self, prompt: str, output_format: str = "text") -> list[str]:
        """Build the command list for agy non-interactive execution."""
        return [
            self.executable_path,
            "-p", prompt,
            "--model", self.model,
            "--effort", self.effort,
            "--output-format", output_format,
        ]

    def _invoke_sync(self, prompt: str) -> Tuple[bool, str, str]:
        """
        Synchronously invoke agy in detached mode.
        Returns: (success: bool, output: str, error: str)
        """
        cmd = self.build_command(prompt)
        creation_flags = 0
        if os.name == "nt":
            # On Windows, run in detached/no-window mode without an interactive console lock
            creation_flags = CREATE_NO_WINDOW

        start_time = time.time()
        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creation_flags,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            stdout, stderr = process.communicate(timeout=self.timeout)
            duration = time.time() - start_time

            if process.returncode == 0:
                logger.debug(f"agy completed successfully in {duration:.2f}s")
                return True, stdout.strip(), stderr.strip()
            else:
                error_msg = f"agy failed (code {process.returncode}) after {duration:.2f}s: {stderr.strip()}"
                logger.error(error_msg)
                return False, stdout.strip(), error_msg

        except subprocess.TimeoutExpired:
            process.kill()
            err = f"agy timed out after {self.timeout}s"
            logger.error(err)
            return False, "", err
        except Exception as e:
            err = f"Failed to execute agy: {str(e)}"
            logger.error(err)
            return False, "", err

    async def invoke_async(self, prompt: str, retries: int = 1) -> str:
        """
        Asynchronously invoke agy in detached mode using an event loop thread.
        Includes optional retry logic for robustness.
        """
        loop = asyncio.get_running_loop()
        last_error = ""

        for attempt in range(retries + 1):
            success, stdout, stderr = await loop.run_in_executor(None, self._invoke_sync, prompt)
            if success and stdout:
                return stdout
            
            last_error = stderr or "Empty output received"
            if attempt < retries:
                logger.warning(f"Retrying agy invocation (attempt {attempt + 1}/{retries}) due to: {last_error}")
                await asyncio.sleep(2)

        raise RuntimeError(f"Antigravity CLI invocation failed: {last_error}")
