import asyncio
import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, AsyncMock

from board.config import SESSIONS_DIR, DEFAULT_MODEL, DEFAULT_EFFORT
from board.orchestrator import BoardOrchestrator
from board.cli_ui import render_slash_menu
from board.cli_completer import BoardSlashCompleter, SLASH_COMMANDS
from prompt_toolkit.document import Document
from main import (
    parse_args,
    parse_command,
    check_command_chaining,
    handle_slash_trigger,
    handle_history_command,
    handle_delete_command,
    handle_cls_command,
    handle_new_command,
    show_help,
    show_memories,
)

class TestSlashCommands(unittest.TestCase):

    def test_parse_command(self):
        """Verify command parser handles all slash and keyword variants."""
        # Slash trigger
        cmd, arg = parse_command("/")
        self.assertEqual(cmd, "slash")

        cmd, arg = parse_command("/?")
        self.assertEqual(cmd, "slash")

        cmd, arg = parse_command("/menu")
        self.assertEqual(cmd, "slash")

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

        # Cls variants
        cmd, arg = parse_command("/cls")
        self.assertEqual(cmd, "cls")
        self.assertEqual(arg, "")

        cmd, arg = parse_command("cls")
        self.assertEqual(cmd, "cls")

        cmd, arg = parse_command("/clear")
        self.assertEqual(cmd, "clear")

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

    def test_prevent_chaining_slash_commands(self):
        """Verify command chaining detection prevents chained commands in all forms."""
        # 1. Chained space-separated commands
        is_chained, err = check_command_chaining("/history /new")
        self.assertTrue(is_chained)
        self.assertIn("Command chaining is not allowed", err)

        is_chained, err = check_command_chaining("/new /cls")
        self.assertTrue(is_chained)
        self.assertIn("Command chaining is not allowed", err)

        is_chained, err = check_command_chaining("/plan /advisors")
        self.assertTrue(is_chained)
        self.assertIn("Command chaining is not allowed", err)

        is_chained, err = check_command_chaining("/delete 1 /plan")
        self.assertTrue(is_chained)
        self.assertIn("Command chaining is not allowed", err)

        # 2. Chained keywords without second slash
        is_chained, err = check_command_chaining("/history new")
        self.assertTrue(is_chained)
        self.assertIn("Command chaining is not allowed", err)

        is_chained, err = check_command_chaining("/plan advisors")
        self.assertTrue(is_chained)
        self.assertIn("Command chaining is not allowed", err)

        # 3. Separator-based chaining (&&, ||, ;, |, &)
        is_chained, err = check_command_chaining("/history && /new")
        self.assertTrue(is_chained)
        self.assertIn("&&", err)

        is_chained, err = check_command_chaining("/plan ; /advisors")
        self.assertTrue(is_chained)
        self.assertIn(";", err)

        is_chained, err = check_command_chaining("/new & /cls")
        self.assertTrue(is_chained)
        self.assertIn("&", err)

        is_chained, err = check_command_chaining("/history | /plan")
        self.assertTrue(is_chained)
        self.assertIn("|", err)

        # 4. Multiple consecutive slashes
        is_chained, err = check_command_chaining("//new")
        self.assertTrue(is_chained)
        self.assertIn("Multiple consecutive slashes", err)

        is_chained, err = check_command_chaining("///help")
        self.assertTrue(is_chained)
        self.assertIn("Multiple consecutive slashes", err)

        # 5. Concatenated slash commands
        is_chained, err = check_command_chaining("/history/new")
        self.assertTrue(is_chained)
        self.assertIn("Chained slash commands detected", err)

        # 6. Valid non-chained commands must pass through
        is_chained, err = check_command_chaining("/")
        self.assertFalse(is_chained)
        self.assertIsNone(err)

        is_chained, err = check_command_chaining("/new Should we launch next month?")
        self.assertFalse(is_chained)
        self.assertIsNone(err)

        is_chained, err = check_command_chaining("/new We need 24/7 technical support")
        self.assertFalse(is_chained)
        self.assertIsNone(err)

        is_chained, err = check_command_chaining("Should we launch on 2026/11/15 or wait?")
        self.assertFalse(is_chained)
        self.assertIsNone(err)

    def test_board_slash_completer_shows_options_on_slash(self):
        """Verify BoardSlashCompleter instantly yields all options when '/' is typed (Claude/Antigravity style)."""
        completer = BoardSlashCompleter()
        doc = Document("/")
        completions = list(completer.get_completions(doc, None))

        # Must yield all 9 slash commands
        self.assertEqual(len(completions), len(SLASH_COMMANDS))
        comp_texts = [c.text for c in completions]
        self.assertIn("/new", comp_texts)
        self.assertIn("/history", comp_texts)
        self.assertIn("/delete", comp_texts)
        self.assertIn("/cls", comp_texts)
        self.assertIn("/advisors", comp_texts)
        self.assertIn("/plan", comp_texts)
        self.assertIn("/memory", comp_texts)
        self.assertIn("/help", comp_texts)
        self.assertIn("/exit", comp_texts)

        # Verify descriptions (display_meta) are populated
        for c in completions:
            self.assertTrue(len(str(c.display_meta)) > 5)

        # Verify real-time prefix filtering: typing '/h' filters down to '/history' and '/help'
        doc_h = Document("/h")
        comps_h = list(completer.get_completions(doc_h, None))
        self.assertEqual(len(comps_h), 2)
        self.assertSetEqual({c.text for c in comps_h}, {"/history", "/help"})

    def test_board_slash_completer_prevents_chaining(self):
        """Verify BoardSlashCompleter suppresses completions if space or chained command is present."""
        completer = BoardSlashCompleter()

        # Once a space is typed (e.g. '/new '), no slash commands should be suggested
        doc_spaced = Document("/new ")
        comps_spaced = list(completer.get_completions(doc_spaced, None))
        self.assertEqual(len(comps_spaced), 0)

        # Chained attempt in prompt
        doc_chained = Document("/new /")
        comps_chained = list(completer.get_completions(doc_chained, None))
        self.assertEqual(len(comps_chained), 0)

    def test_board_slash_completer_advisor_mentions(self):
        """Verify BoardSlashCompleter yields advisor @tag completions when typing '@'."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()

        completer = BoardSlashCompleter(get_advisors_fn=lambda: orchestrator.advisors)
        doc_at = Document("@")
        comps_at = list(completer.get_completions(doc_at, None))

        self.assertGreater(len(comps_at), 0)
        first_comp = comps_at[0]
        self.assertTrue(first_comp.text.startswith("@"))

    def test_parse_args_defaults(self):
        """Verify parse_args defaults to DEFAULT_MODEL and DEFAULT_EFFORT."""
        with patch("sys.argv", ["main.py"]):
            args = parse_args()
            self.assertEqual(args.model, DEFAULT_MODEL)
            self.assertEqual(args.effort, DEFAULT_EFFORT)

    def test_parse_args_custom(self):
        """Verify parse_args parses --model and --effort flags and short -m / -e."""
        with patch("sys.argv", ["main.py", "--model", "gemini-2.5-pro", "--effort", "high"]):
            args = parse_args()
            self.assertEqual(args.model, "gemini-2.5-pro")
            self.assertEqual(args.effort, "high")

        with patch("sys.argv", ["main.py", "-m", "custom-flash", "-e", "low"]):
            args = parse_args()
            self.assertEqual(args.model, "custom-flash")
            self.assertEqual(args.effort, "low")

    def test_orchestrator_custom_model_and_effort(self):
        """Verify BoardOrchestrator propagates custom model and effort to invokers and advisors."""
        orchestrator = BoardOrchestrator(model="gemini-2.5-pro", effort="high")
        self.assertEqual(orchestrator.model, "gemini-2.5-pro")
        self.assertEqual(orchestrator.effort, "high")
        self.assertEqual(orchestrator.synthesizer_invoker.model, "gemini-2.5-pro")
        self.assertEqual(orchestrator.synthesizer_invoker.effort, "high")

        orchestrator._load_predefined_advisors()
        for adv in orchestrator.advisors:
            self.assertEqual(adv.model, "gemini-2.5-pro")
            self.assertEqual(adv.effort, "high")
            self.assertEqual(adv.invoker.model, "gemini-2.5-pro")
            self.assertEqual(adv.invoker.effort, "high")

    def test_session_creation_loading_and_deletion(self):
        """Verify session JSON persistence, listing, loading, and deletion."""
        orchestrator = BoardOrchestrator()
        test_session_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        test_file = SESSIONS_DIR / f"session_{test_session_id}.json"

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

        # Check listing
        sessions = orchestrator.list_saved_sessions()
        session_ids = [s["session_id"] for s in sessions]
        self.assertIn(test_session_id, session_ids)

        # Check loading
        loaded = orchestrator.load_session_by_id(test_session_id)
        self.assertTrue(loaded)
        self.assertEqual(orchestrator.current_problem, "Should we pivot from B2C to B2B SaaS?")
        self.assertEqual(len(orchestrator.advisors), 1)
        self.assertEqual(orchestrator.advisors[0].name, "Marcus Vance")
        self.assertEqual(len(orchestrator.messages), 2)
        self.assertEqual(orchestrator.final_plan, "Pivot conditionally within 90 days.")

        # Check deletion
        deleted = orchestrator.delete_session_by_id(test_session_id)
        self.assertTrue(deleted)
        self.assertFalse(test_file.exists())

        sessions_after = orchestrator.list_saved_sessions()
        ids_after = [s["session_id"] for s in sessions_after]
        self.assertNotIn(test_session_id, ids_after)


class TestAsyncCommandFlows(unittest.IsolatedAsyncioTestCase):

    async def test_handle_slash_trigger_shows_options_menu(self):
        """Verify giving '/' displays the options menu and executes selected option."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        orchestrator.final_plan = "Mock Action Plan"

        # User gives '/' -> menu shown -> selects '6' (/plan)
        with patch("rich.prompt.Prompt.ask", return_value="6"), \
             patch("main.render_plan") as mock_render_plan:
            res = await handle_slash_trigger(orchestrator)
            self.assertTrue(res)
            mock_render_plan.assert_called_once_with("Mock Action Plan")

    async def test_handle_slash_trigger_numeric_help(self):
        """Verify selecting '8' in slash menu shows help."""
        orchestrator = BoardOrchestrator()
        with patch("rich.prompt.Prompt.ask", return_value="8"), \
             patch("main.show_help") as mock_help:
            res = await handle_slash_trigger(orchestrator)
            self.assertTrue(res)
            mock_help.assert_called_once()

    async def test_handle_slash_trigger_cancel(self):
        """Verify pressing Enter in slash menu cancels cleanly."""
        orchestrator = BoardOrchestrator()
        with patch("rich.prompt.Prompt.ask", return_value=""):
            res = await handle_slash_trigger(orchestrator)
            self.assertFalse(res)

    async def test_handle_slash_trigger_chained_input_rejected(self):
        """Verify chained input in slash options prompt is blocked."""
        orchestrator = BoardOrchestrator()
        with patch("rich.prompt.Prompt.ask", return_value="/new /history"):
            res = await handle_slash_trigger(orchestrator)
            self.assertFalse(res)

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

        sessions = orchestrator.list_saved_sessions()
        target_idx = None
        for i, s in enumerate(sessions, 1):
            if s["session_id"] == test_session_id:
                target_idx = i
                break

        self.assertIsNotNone(target_idx)

        prompt_inputs = [f"d {target_idx}", "y", ""]
        with patch("rich.prompt.Prompt.ask", side_effect=prompt_inputs):
            res = await handle_history_command(orchestrator)
            self.assertFalse(res)

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

        with patch("rich.prompt.Prompt.ask", return_value=str(target_idx)):
            res = await handle_history_command(orchestrator)
            self.assertTrue(res)
            self.assertEqual(orchestrator.session_id, test_session_id)
            self.assertEqual(orchestrator.current_problem, "Test Problem to Load")

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

        with patch("rich.prompt.Prompt.ask", return_value="y"):
            await handle_delete_command(orchestrator, str(target_idx))

        self.assertFalse(test_file.exists())

    def test_orchestrator_clear_session_preserves_session_id(self):
        """Verify clear_session clears advisors, problem, messages, and plan in the SAME session without changing session_id."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        orchestrator.current_problem = "Existing strategic dilemma"
        orchestrator.final_plan = "Existing action plan"
        original_session_id = orchestrator.session_id

        returned_id = orchestrator.clear_session()
        self.assertEqual(returned_id, original_session_id)
        self.assertEqual(orchestrator.session_id, original_session_id)
        self.assertEqual(orchestrator.current_problem, "")
        self.assertEqual(orchestrator.final_plan, "")
        self.assertEqual(orchestrator.advisors, [])
        self.assertEqual(orchestrator.messages, [])

    def test_handle_cls_command(self):
        """Verify /cls command clears session state and resets slate without generating a new session."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        orchestrator.current_problem = "Some dilemma"
        original_id = orchestrator.session_id

        with patch("rich.console.Console.clear"):
            handle_cls_command(orchestrator)

        self.assertEqual(orchestrator.session_id, original_id)
        self.assertEqual(orchestrator.current_problem, "")
        self.assertEqual(orchestrator.advisors, [])
        self.assertEqual(orchestrator.final_plan, "")

    async def test_handle_new_command_resets_session(self):
        """Verify /new resets session and triggers fresh deliberation."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        orchestrator.current_problem = "Old problem"
        old_session_id = orchestrator.session_id

        with patch("main.run_problem_session", new_callable=AsyncMock) as mock_run:
            await handle_new_command(orchestrator, "Brand new startup dilemma")
            mock_run.assert_awaited_once_with(orchestrator, "Brand new startup dilemma")

        self.assertNotEqual(orchestrator.session_id, old_session_id)
        self.assertEqual(orchestrator.current_problem, "")
        self.assertEqual(orchestrator.advisors, [])

    async def test_ask_input_async_execution_no_warnings(self):
        """Verify ask_input executes cleanly as an awaited coroutine in active asyncio loop without RuntimeWarning."""
        import warnings
        from main import ask_input
        with warnings.catch_warnings(record=True) as w, \
             patch("rich.prompt.Prompt.ask", return_value="test input"):
            res = await ask_input("Prompt Rich", "<b>Prompt HTML</b>")
            self.assertEqual(res, "test input")
            runtime_warnings = [item for item in w if issubclass(item.category, RuntimeWarning)]
            self.assertEqual(len(runtime_warnings), 0)

    async def test_session_model_and_effort_persistence(self):
        """Verify session JSON saves and restores custom model and effort settings."""
        orchestrator = BoardOrchestrator(model="custom-exp-model", effort="high")
        test_session_id = f"test_meta_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        test_file = SESSIONS_DIR / f"session_{test_session_id}.json"

        orchestrator.session_id = test_session_id
        orchestrator._load_predefined_advisors()
        orchestrator._save_session_memories("Test dilemma", "Test plan")

        self.assertTrue(test_file.exists())
        with open(test_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("model"), "custom-exp-model")
        self.assertEqual(data.get("effort"), "high")

        # Now load with a new orchestrator and verify model/effort are restored
        new_orchestrator = BoardOrchestrator()
        new_orchestrator.load_session_by_id(test_session_id)
        self.assertEqual(new_orchestrator.model, "custom-exp-model")
        self.assertEqual(new_orchestrator.effort, "high")
        self.assertEqual(new_orchestrator.synthesizer_invoker.model, "custom-exp-model")
        self.assertEqual(new_orchestrator.synthesizer_invoker.effort, "high")

        test_file.unlink(missing_ok=True)

    async def test_evaluate_user_input_need_no_indicators_skips_llm(self):
        """Verify that plain statements without questions or user/constraint indicators skip LLM reading."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        advisor = orchestrator.advisors[0]
        statement = "We should focus on organic growth and improving gross margins this quarter."

        with patch.object(orchestrator.synthesizer_invoker, "invoke_async", new_callable=AsyncMock) as mock_invoke:
            result = await orchestrator.evaluate_user_input_need(advisor, statement, "Test dilemma")
            mock_invoke.assert_not_called()
            self.assertIsNone(result)

    async def test_evaluate_user_input_need_rejects_casual_user_mention(self):
        """Verify orchestrator reads and rejects casual/historical mentions of @User without interrupting."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        advisor = orchestrator.advisors[0]
        statement = "As @User mentioned in the initial problem, runway is 12 months, so @Marcus is mistaken."

        llm_reply = (
            "NEEDS_USER_INPUT: NO\n"
            "REASON: The advisor is merely citing context already provided in the original dilemma."
        )

        with patch.object(orchestrator.synthesizer_invoker, "invoke_async", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = llm_reply
            result = await orchestrator.evaluate_user_input_need(advisor, statement, "Test dilemma")
            mock_invoke.assert_called_once()
            self.assertIsNone(result)

    async def test_evaluate_user_input_need_rejects_rhetorical_question(self):
        """Verify orchestrator reads and rejects rhetorical debate questions."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        advisor = orchestrator.advisors[0]
        statement = "Would @User want to risk 60% equity dilution on an unproven pivot? Of course not."

        llm_reply = (
            "NEEDS_USER_INPUT: NO\n"
            "REASON: Rhetorical question already answered directly by the advisor in their statement."
        )

        with patch.object(orchestrator.synthesizer_invoker, "invoke_async", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = llm_reply
            result = await orchestrator.evaluate_user_input_need(advisor, statement, "Test dilemma")
            mock_invoke.assert_called_once()
            self.assertIsNone(result)

    async def test_evaluate_user_input_need_approves_genuine_user_input_request(self):
        """Verify orchestrator reads scenario and approves genuine missing fact inquiry."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        advisor = orchestrator.advisors[0]
        statement = "We cannot model profitability without private metrics: @User, what is your net monthly burn rate?"

        llm_reply = (
            "NEEDS_USER_INPUT: YES\n"
            "QUESTION: What is your net monthly burn rate?"
        )

        with patch.object(orchestrator.synthesizer_invoker, "invoke_async", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = llm_reply
            result = await orchestrator.evaluate_user_input_need(advisor, statement, "Test dilemma")
            mock_invoke.assert_called_once()
            self.assertEqual(result, "What is your net monthly burn rate?")

    async def test_evaluate_user_input_need_approves_without_explicit_user_keyword(self):
        """Verify orchestrator reads scenario and approves critical question even without '@User' tag."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        advisor = orchestrator.advisors[0]
        statement = "Before choosing between Series A or bootstrapping, what is the founder's personal timeline for an exit?"

        llm_reply = (
            "NEEDS_USER_INPUT: YES\n"
            "QUESTION: What is your personal timeline and preferred horizon for an exit?"
        )

        with patch.object(orchestrator.synthesizer_invoker, "invoke_async", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = llm_reply
            result = await orchestrator.evaluate_user_input_need(advisor, statement, "Test dilemma")
            mock_invoke.assert_called_once()
            self.assertEqual(result, "What is your personal timeline and preferred horizon for an exit?")

    async def test_evaluate_user_input_need_fallback_on_invoker_failure(self):
        """Verify safe fallback when invoker raises an unexpected error."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        advisor = orchestrator.advisors[0]

        # Case A: Casual mention with exception -> defaults to None (no false interruption)
        statement_casual = "As @User said earlier, we should proceed carefully."
        with patch.object(orchestrator.synthesizer_invoker, "invoke_async", side_effect=RuntimeError("CLI failure")):
            res_casual = await orchestrator.evaluate_user_input_need(advisor, statement_casual, "Test dilemma")
            self.assertIsNone(res_casual)

        # Case B: Explicit @User question with question mark -> falls back to question extraction
        statement_direct = "@User, can you confirm if the budget is under $50k?"
        with patch.object(orchestrator.synthesizer_invoker, "invoke_async", side_effect=RuntimeError("CLI failure")):
            res_direct = await orchestrator.evaluate_user_input_need(advisor, statement_direct, "Test dilemma")
            self.assertIsNotNone(res_direct)
            self.assertIn("@User", res_direct)

    async def test_deliberation_flow_user_input_validated_by_chair(self):
        """Verify deliberation flow suspends only when orchestrator reads and validates user input need."""
        user_input_called = False

        async def mock_user_callback(advisor, question):
            nonlocal user_input_called
            user_input_called = True
            return "Our maximum acceptable burn is $10k/month."

        orchestrator = BoardOrchestrator(user_input_callback=mock_user_callback)
        orchestrator._load_predefined_advisors()
        # Keep only 2 advisors for fast test execution
        orchestrator.advisors = orchestrator.advisors[:2]
        orchestrator.advisors_by_tag = {a.tag.lower(): a for a in orchestrator.advisors}
        orchestrator.max_rounds = 2

        # Round 1: Advisor 0 mentions @User casually (should NOT trigger callback)
        # Round 1: Advisor 1 asks a real question (orchestrator approves, SHOULD trigger callback)
        adv0_resp = "As @User said, our focus is B2B. @David, do you agree?"
        adv1_resp = "I need clarity: what is your max burn rate? @User please clarify."

        async def mock_initial_assessment(problem, all_advisors, user_notes=""):
            return adv0_resp

        orchestrator.advisors[0].generate_initial_assessment = AsyncMock(return_value=adv0_resp)
        orchestrator.advisors[1].generate_initial_assessment = AsyncMock(return_value=adv1_resp)
        orchestrator.advisors[0].generate_discussion_turn = AsyncMock(return_value="Final conclusion.")
        orchestrator.advisors[1].generate_discussion_turn = AsyncMock(return_value="Final conclusion.")

        # Mock evaluate_user_input_need to return None for adv0, and a question for adv1
        async def mock_evaluate(adv, text, prob=None, ctx=None):
            if "max burn" in text:
                return "What is your maximum acceptable burn rate?"
            return None

        orchestrator.evaluate_user_input_need = mock_evaluate
        orchestrator._synthesize_action_plan = AsyncMock(return_value="Action Plan")
        orchestrator._save_session_memories = lambda p, plan: None

        plan = await orchestrator.run_deliberation("Test problem")
        self.assertEqual(plan, "Action Plan")
        self.assertTrue(user_input_called)

        # Check recorded messages to verify user input was incorporated
        user_msgs = [m for m in orchestrator.messages if m.sender == "USER" and m.stage == "round_1_user_input"]
        self.assertEqual(len(user_msgs), 1)
        self.assertIn("10k/month", user_msgs[0].content)


if __name__ == "__main__":
    unittest.main()
