import asyncio
import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, AsyncMock

from board.config import SESSIONS_DIR
from board.orchestrator import BoardOrchestrator
from main import (
    parse_command,
    handle_history_command,
    handle_delete_command,
    handle_suspend_command,
    handle_new_command,
    show_help,
    show_memories,
)

class TestSlashCommands(unittest.TestCase):

    def test_parse_command(self):
        """Verify command parser handles all slash and keyword variants."""
        # Help
        cmd, arg = parse_command("/help")
        self.assertEqual(cmd, "help")
        self.assertEqual(arg, "")

        cmd, arg = parse_command("help")
        self.assertEqual(cmd, "help")

        # History
        cmd, arg = parse_command("/history")
        self.assertEqual(cmd, "history")
        self.assertEqual(arg, "")

        cmd, arg = parse_command("history")
        self.assertEqual(cmd, "history")

        # New with and without args
        cmd, arg = parse_command("/new")
        self.assertEqual(cmd, "new")
        self.assertEqual(arg, "")

        cmd, arg = parse_command("/new Should we expand to Europe?")
        self.assertEqual(cmd, "new")
        self.assertEqual(arg, "Should we expand to Europe?")

        # Suspend with and without args
        cmd, arg = parse_command("/suspend")
        self.assertEqual(cmd, "suspend")
        self.assertEqual(arg, "")

        cmd, arg = parse_command("/suspend Pivot to enterprise sales")
        self.assertEqual(cmd, "suspend")
        self.assertEqual(arg, "Pivot to enterprise sales")

        # Delete variants
        cmd, arg = parse_command("/delete 2")
        self.assertEqual(cmd, "delete")
        self.assertEqual(arg, "2")

        cmd, arg = parse_command("/del 3")
        self.assertEqual(cmd, "del")
        self.assertEqual(arg, "3")

        cmd, arg = parse_command("rm 1")
        self.assertEqual(cmd, "rm")
        self.assertEqual(arg, "1")

        # Non-commands (actual problem inputs or follow-ups)
        cmd, arg = parse_command("Should we launch our product next Monday?")
        self.assertIsNone(cmd)
        self.assertEqual(arg, "Should we launch our product next Monday?")

        cmd, arg = parse_command("@Elena what are the main patent risks?")
        self.assertIsNone(cmd)
        self.assertEqual(arg, "@Elena what are the main patent risks?")

        cmd, arg = parse_command("")
        self.assertIsNone(cmd)
        self.assertEqual(arg, "")

    def test_session_creation_loading_and_deletion(self):
        """Verify session JSON persistence, listing, loading, and deletion."""
        orchestrator = BoardOrchestrator()
        test_session_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        test_file = SESSIONS_DIR / f"session_{test_session_id}.json"

        # 1. Create a dummy test session file
        dummy_data = {
            "session_id": test_session_id,
            "timestamp": datetime.now().isoformat(),
            "problem": "Should we pivot from B2C to B2B SaaS?",
            "advisors": [
                {
                    "id": "marcus",
                    "name": "Marcus Vance",
                    "tag": "@Marcus",
                    "role": "Chief Revenue Officer",
                    "avatar": "⚡",
                    "color": "yellow",
                    "persona": "Aggressive B2B sales leader.",
                    "bio": "Veteran SaaS sales leader.",
                    "core_beliefs": ["Enterprise revenue compounds faster."],
                }
            ],
            "messages": [
                {
                    "sender": "USER",
                    "tag": "@User",
                    "content": "Should we pivot from B2C to B2B SaaS?",
                    "stage": "problem",
                },
                {
                    "sender": "Marcus Vance",
                    "tag": "@Marcus",
                    "content": "B2B SaaS provides predictable ACV and lower churn.",
                    "stage": "round_1_opening",
                }
            ],
            "final_plan": "Pivot conditionally within 90 days.",
        }

        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(dummy_data, f, indent=2)

        self.assertTrue(test_file.exists())

        # 2. Check listing
        sessions = orchestrator.list_saved_sessions()
        session_ids = [s["session_id"] for s in sessions]
        self.assertIn(test_session_id, session_ids)

        # 3. Check loading
        loaded = orchestrator.load_session_by_id(test_session_id)
        self.assertTrue(loaded)
        self.assertEqual(orchestrator.current_problem, "Should we pivot from B2C to B2B SaaS?")
        self.assertEqual(len(orchestrator.advisors), 1)
        self.assertEqual(orchestrator.advisors[0].name, "Marcus Vance")
        self.assertEqual(len(orchestrator.messages), 2)
        self.assertEqual(orchestrator.final_plan, "Pivot conditionally within 90 days.")

        # 4. Check deletion
        deleted = orchestrator.delete_session_by_id(test_session_id)
        self.assertTrue(deleted)
        self.assertFalse(test_file.exists())

        # Listing after delete should not include test session
        sessions_after = orchestrator.list_saved_sessions()
        ids_after = [s["session_id"] for s in sessions_after]
        self.assertNotIn(test_session_id, ids_after)


class TestAsyncCommandFlows(unittest.IsolatedAsyncioTestCase):

    async def test_handle_history_command_delete_flow(self):
        """Simulate user navigating /history and deleting a session with 'd #'."""
        orchestrator = BoardOrchestrator()
        test_session_id = f"test_hist_del_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        test_file = SESSIONS_DIR / f"session_{test_session_id}.json"

        with open(test_file, "w", encoding="utf-8") as f:
            json.dump({
                "session_id": test_session_id,
                "timestamp": datetime.now().isoformat(),
                "problem": "Test Problem for History Deletion",
                "advisors": [],
                "messages": [],
                "final_plan": "Test Plan",
            }, f)

        # Find 1-based index of this session
        sessions = orchestrator.list_saved_sessions()
        target_idx = None
        for i, s in enumerate(sessions, 1):
            if s["session_id"] == test_session_id:
                target_idx = i
                break

        self.assertIsNotNone(target_idx)

        # User inputs: 'd <target_idx>', then confirm 'y', then '' (press enter to return)
        prompt_inputs = [f"d {target_idx}", "y", ""]
        with patch("rich.prompt.Prompt.ask", side_effect=prompt_inputs):
            res = await handle_history_command(orchestrator)
            self.assertFalse(res)  # Returned without loading a session

        # Verify session was deleted
        self.assertFalse(test_file.exists())

    async def test_handle_history_command_load_flow(self):
        """Simulate user selecting a session to load."""
        orchestrator = BoardOrchestrator()
        test_session_id = f"test_hist_load_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        test_file = SESSIONS_DIR / f"session_{test_session_id}.json"

        with open(test_file, "w", encoding="utf-8") as f:
            json.dump({
                "session_id": test_session_id,
                "timestamp": datetime.now().isoformat(),
                "problem": "Test Problem to Load",
                "advisors": [],
                "messages": [],
                "final_plan": "Test Plan",
            }, f)

        sessions = orchestrator.list_saved_sessions()
        target_idx = None
        for i, s in enumerate(sessions, 1):
            if s["session_id"] == test_session_id:
                target_idx = i
                break

        self.assertIsNotNone(target_idx)

        # User enters session number
        with patch("rich.prompt.Prompt.ask", return_value=str(target_idx)):
            res = await handle_history_command(orchestrator)
            self.assertTrue(res)  # Successfully loaded
            self.assertEqual(orchestrator.session_id, test_session_id)
            self.assertEqual(orchestrator.current_problem, "Test Problem to Load")

        # Cleanup
        test_file.unlink(missing_ok=True)

    async def test_handle_delete_command_direct(self):
        """Simulate /delete <#> direct command."""
        orchestrator = BoardOrchestrator()
        test_session_id = f"test_direct_del_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        test_file = SESSIONS_DIR / f"session_{test_session_id}.json"

        with open(test_file, "w", encoding="utf-8") as f:
            json.dump({
                "session_id": test_session_id,
                "timestamp": datetime.now().isoformat(),
                "problem": "Direct Delete Test",
                "advisors": [],
                "messages": [],
            }, f)

        sessions = orchestrator.list_saved_sessions()
        target_idx = None
        for i, s in enumerate(sessions, 1):
            if s["session_id"] == test_session_id:
                target_idx = i
                break

        # Call handle_delete_command with target_idx and confirm 'y'
        with patch("rich.prompt.Prompt.ask", return_value="y"):
            await handle_delete_command(orchestrator, str(target_idx))

        self.assertFalse(test_file.exists())

    async def test_handle_suspend_command_no_advisors(self):
        """Verify /suspend when no board is assembled warns cleanly without error."""
        orchestrator = BoardOrchestrator()
        orchestrator.advisors = []
        # Should return without raising
        await handle_suspend_command(orchestrator, "New problem")

    async def test_handle_suspend_command_with_pivot(self):
        """Verify /suspend pivots in the same session with advisors preserved."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        original_session_id = orchestrator.session_id
        original_advisors_count = len(orchestrator.advisors)

        with patch.object(orchestrator, "suspend_and_pivot", new_callable=AsyncMock) as mock_pivot:
            mock_pivot.return_value = "Synthesized pivot action plan"
            await handle_suspend_command(orchestrator, "Focus on cybersecurity compliance")
            mock_pivot.assert_awaited_once_with("Focus on cybersecurity compliance")

        self.assertEqual(orchestrator.session_id, original_session_id)
        self.assertEqual(len(orchestrator.advisors), original_advisors_count)

    async def test_handle_new_command_resets_session(self):
        """Verify /new resets session and triggers fresh deliberation."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        orchestrator.current_problem = "Old problem"
        old_session_id = orchestrator.session_id

        with patch("main.run_problem_session", new_callable=AsyncMock) as mock_run:
            await handle_new_command(orchestrator, "Brand new startup dilemma")
            mock_run.assert_awaited_once_with(orchestrator, "Brand new startup dilemma")

        # Session ID should have changed and previous state reset
        self.assertNotEqual(orchestrator.session_id, old_session_id)
        self.assertEqual(orchestrator.current_problem, "")
        self.assertEqual(orchestrator.advisors, [])


if __name__ == "__main__":
    unittest.main()
