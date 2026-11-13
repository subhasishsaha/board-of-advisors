import asyncio
import json
import warnings
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, AsyncMock
import pytest
from prompt_toolkit.document import Document

from board.config import SESSIONS_DIR, DEFAULT_MODEL, DEFAULT_EFFORT
from board.orchestrator import BoardOrchestrator
from board.cli_ui import render_slash_menu
from board.cli_completer import BoardSlashCompleter, SLASH_COMMANDS
from main import (
    parse_args,
    parse_command,
    check_command_chaining,
    validate_integer_arg,
    handle_set_max_agents_command,
    handle_set_round_tables_command,
    handle_slash_trigger,
    handle_history_command,
    handle_delete_command,
    handle_cls_command,
    handle_new_command,
    show_help,
    show_memories,
    ask_input,
)


class TestSlashCommandParsing:
    """Tests for CLI command parsing and routing."""

    def test_parse_command(self):
        """Verify command parser handles all slash and keyword variants."""
        # Slash trigger
        cmd, arg = parse_command("/")
        assert cmd == "slash"

        cmd, arg = parse_command("/?")
        assert cmd == "slash"

        cmd, arg = parse_command("/menu")
        assert cmd == "slash"

        # Help
        cmd, arg = parse_command("/help")
        assert cmd == "help"
        assert arg == ""

        cmd, arg = parse_command("help")
        assert cmd == "help"

        # History
        cmd, arg = parse_command("/history")
        assert cmd == "history"
        assert arg == ""

        cmd, arg = parse_command("history")
        assert cmd == "history"

        # New with and without args
        cmd, arg = parse_command("/new")
        assert cmd == "new"
        assert arg == ""

        cmd, arg = parse_command("/new Should we expand to Europe?")
        assert cmd == "new"
        assert arg == "Should we expand to Europe?"

        # Cls variants
        cmd, arg = parse_command("/cls")
        assert cmd == "cls"
        assert arg == ""

        cmd, arg = parse_command("cls")
        assert cmd == "cls"

        cmd, arg = parse_command("/clear")
        assert cmd == "clear"

        # Delete variants
        cmd, arg = parse_command("/delete 2")
        assert cmd == "delete"
        assert arg == "2"

        cmd, arg = parse_command("/del 3")
        assert cmd == "del"
        assert arg == "3"

        cmd, arg = parse_command("rm 1")
        assert cmd == "rm"
        assert arg == "1"

        # Non-commands (actual problem inputs or follow-ups)
        cmd, arg = parse_command("Should we launch our product next Monday?")
        assert cmd is None
        assert arg == "Should we launch our product next Monday?"

        cmd, arg = parse_command("@Elena what are the main patent risks?")
        assert cmd is None
        assert arg == "@Elena what are the main patent risks?"

        cmd, arg = parse_command("")
        assert cmd is None
        assert arg == ""

    def test_parse_command_set_max_agents_and_rounds(self):
        """Verify parser resolves all aliases for set-max-agents and set-round-tables."""
        # set-max-agents
        cmd, arg = parse_command("/set-max-agents 6")
        assert cmd == "set-max-agents"
        assert arg == "6"

        cmd, arg = parse_command("/set_max_agents 8")
        assert cmd == "set-max-agents"
        assert arg == "8"

        cmd, arg = parse_command("/max-agents 5")
        assert cmd == "set-max-agents"
        assert arg == "5"

        cmd, arg = parse_command("set-max-agents 7")
        assert cmd == "set-max-agents"
        assert arg == "7"

        # set-round-tables
        cmd, arg = parse_command("/set-round-tables 4")
        assert cmd == "set-round-tables"
        assert arg == "4"

        cmd, arg = parse_command("/set_round_tables 2")
        assert cmd == "set-round-tables"
        assert arg == "2"

        cmd, arg = parse_command("/round-tables 5")
        assert cmd == "set-round-tables"
        assert arg == "5"

        cmd, arg = parse_command("/rounds 3")
        assert cmd == "set-round-tables"
        assert arg == "3"


class TestCommandChainingPrevention:
    """Tests for preventing chained slash commands and shell operators."""

    def test_prevent_chaining_slash_commands(self):
        """Verify command chaining detection prevents chained commands in all forms."""
        # 1. Chained space-separated commands
        is_chained, err = check_command_chaining("/history /new")
        assert is_chained
        assert "Command chaining is not allowed" in err

        is_chained, err = check_command_chaining("/new /cls")
        assert is_chained
        assert "Command chaining is not allowed" in err

        is_chained, err = check_command_chaining("/plan /advisors")
        assert is_chained
        assert "Command chaining is not allowed" in err

        is_chained, err = check_command_chaining("/delete 1 /plan")
        assert is_chained
        assert "Command chaining is not allowed" in err

        # 2. Chained keywords without second slash
        is_chained, err = check_command_chaining("/history new")
        assert is_chained
        assert "Command chaining is not allowed" in err

        is_chained, err = check_command_chaining("/plan advisors")
        assert is_chained
        assert "Command chaining is not allowed" in err

        # 3. Separator-based chaining (&&, ||, ;, |, &)
        is_chained, err = check_command_chaining("/history && /new")
        assert is_chained
        assert "&&" in err

        is_chained, err = check_command_chaining("/plan ; /advisors")
        assert is_chained
        assert ";" in err

        is_chained, err = check_command_chaining("/new & /cls")
        assert is_chained
        assert "&" in err

        is_chained, err = check_command_chaining("/history | /plan")
        assert is_chained
        assert "|" in err

        # 4. Multiple consecutive slashes
        is_chained, err = check_command_chaining("//new")
        assert is_chained
        assert "Multiple consecutive slashes" in err

        is_chained, err = check_command_chaining("///help")
        assert is_chained
        assert "Multiple consecutive slashes" in err

        # 5. Concatenated slash commands
        is_chained, err = check_command_chaining("/history/new")
        assert is_chained
        assert "Chained slash commands detected" in err

        # 6. Valid non-chained commands must pass through
        is_chained, err = check_command_chaining("/")
        assert not is_chained
        assert err is None

        is_chained, err = check_command_chaining("/new Should we launch next month?")
        assert not is_chained
        assert err is None

        is_chained, err = check_command_chaining("/new We need 24/7 technical support")
        assert not is_chained
        assert err is None

        is_chained, err = check_command_chaining("Should we launch on 2026/11/15 or wait?")
        assert not is_chained
        assert err is None


class TestBoardSlashCompleter:
    """Tests for prompt_toolkit live autocompletion."""

    def test_board_slash_completer_shows_options_on_slash(self):
        """Verify BoardSlashCompleter instantly yields all options when '/' is typed."""
        completer = BoardSlashCompleter()
        doc = Document("/")
        completions = list(completer.get_completions(doc, None))

        assert len(completions) == len(SLASH_COMMANDS)
        comp_texts = [c.text for c in completions]
        assert "/new" in comp_texts
        assert "/history" in comp_texts
        assert "/delete" in comp_texts
        assert "/cls" in comp_texts
        assert "/set-max-agents" in comp_texts
        assert "/set-round-tables" in comp_texts
        assert "/advisors" in comp_texts
        assert "/plan" in comp_texts
        assert "/memory" in comp_texts
        assert "/help" in comp_texts
        assert "/exit" in comp_texts

        # Verify descriptions (display_meta) are populated
        for c in completions:
            assert len(str(c.display_meta)) > 5

        # Verify real-time prefix filtering: typing '/h' filters down to '/history' and '/help'
        doc_h = Document("/h")
        comps_h = list(completer.get_completions(doc_h, None))
        assert len(comps_h) == 2
        assert {c.text for c in comps_h} == {"/history", "/help"}

    def test_board_slash_completer_prevents_chaining(self):
        """Verify BoardSlashCompleter suppresses completions if space or chained command is present."""
        completer = BoardSlashCompleter()

        # Once a space is typed (e.g. '/new '), no slash commands should be suggested
        doc_spaced = Document("/new ")
        comps_spaced = list(completer.get_completions(doc_spaced, None))
        assert len(comps_spaced) == 0

        # Chained attempt in prompt
        doc_chained = Document("/new /")
        comps_chained = list(completer.get_completions(doc_chained, None))
        assert len(comps_chained) == 0

    def test_board_slash_completer_advisor_mentions(self):
        """Verify BoardSlashCompleter yields advisor @tag completions when typing '@'."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()

        completer = BoardSlashCompleter(get_advisors_fn=lambda: orchestrator.advisors)
        doc_at = Document("@")
        comps_at = list(completer.get_completions(doc_at, None))

        assert len(comps_at) > 0
        first_comp = comps_at[0]
        assert first_comp.text.startswith("@")

    def test_cli_completer_includes_set_commands(self):
        """Verify completer yields /set-max-agents and /set-round-tables."""
        completer = BoardSlashCompleter()
        doc = Document("/set")
        completions = [c.text for c in completer.get_completions(doc, None)]
        assert "/set-max-agents" in completions
        assert "/set-round-tables" in completions


class TestCLIArgumentsAndConfiguration:
    """Tests for CLI arguments, model/effort propagation, and settings."""

    def test_parse_args_defaults(self):
        """Verify parse_args defaults to DEFAULT_MODEL and DEFAULT_EFFORT."""
        with patch("sys.argv", ["main.py"]):
            args = parse_args()
            assert args.model == DEFAULT_MODEL
            assert args.effort == DEFAULT_EFFORT

    def test_parse_args_custom(self):
        """Verify parse_args parses --model and --effort flags and short -m / -e."""
        with patch("sys.argv", ["main.py", "--model", "gemini-2.5-pro", "--effort", "high"]):
            args = parse_args()
            assert args.model == "gemini-2.5-pro"
            assert args.effort == "high"

        with patch("sys.argv", ["main.py", "-m", "custom-flash", "-e", "low"]):
            args = parse_args()
            assert args.model == "custom-flash"
            assert args.effort == "low"

    def test_orchestrator_custom_model_and_effort(self):
        """Verify BoardOrchestrator propagates custom model and effort to invokers and advisors."""
        orchestrator = BoardOrchestrator(model="gemini-2.5-pro", effort="high")
        assert orchestrator.model == "gemini-2.5-pro"
        assert orchestrator.effort == "high"
        assert orchestrator.synthesizer_invoker.model == "gemini-2.5-pro"
        assert orchestrator.synthesizer_invoker.effort == "high"

        orchestrator._load_predefined_advisors()
        for adv in orchestrator.advisors:
            assert adv.model == "gemini-2.5-pro"
            assert adv.effort == "high"
            assert adv.invoker.model == "gemini-2.5-pro"
            assert adv.invoker.effort == "high"

    def test_validate_integer_arg(self):
        """Verify strict integer validation: only positive integers pass, everything else is rejected."""
        # Valid positive integers
        val, err = validate_integer_arg("5", "set-max-agents")
        assert val == 5
        assert err is None

        val, err = validate_integer_arg("  10  ", "set-max-agents")
        assert val == 10
        assert err is None

        # Empty / missing value
        val, err = validate_integer_arg("", "set-max-agents")
        assert val is None
        assert "Missing value" in err

        # Floats
        val, err = validate_integer_arg("5.5", "set-max-agents")
        assert val is None
        assert "must be an integer, nothing else" in err

        # Non-numeric text
        val, err = validate_integer_arg("five", "set-max-agents")
        assert val is None
        assert "must be an integer, nothing else" in err

        # Alphanumeric / extra tokens
        val, err = validate_integer_arg("5 advisors", "set-max-agents")
        assert val is None
        assert "must be an integer, nothing else" in err

        val, err = validate_integer_arg("5abc", "set-max-agents")
        assert val is None
        assert "must be an integer, nothing else" in err

        # Zero or negative
        val, err = validate_integer_arg("0", "set-max-agents", min_val=1)
        assert val is None
        assert "at least 1" in err

        val, err = validate_integer_arg("-3", "set-max-agents", min_val=1)
        assert val is None
        assert "at least 1" in err

        # Exceeding max_val
        val, err = validate_integer_arg("25", "set-max-agents", min_val=1, max_val=20)
        assert val is None
        assert "cannot exceed 20" in err

    def test_handle_set_max_agents_command(self):
        """Verify setting max dynamic advisors on current thread and pruning active board if necessary."""
        orchestrator = BoardOrchestrator()
        assert orchestrator.max_agents == 10

        # Successfully set max_agents
        res = handle_set_max_agents_command(orchestrator, "6")
        assert res
        assert orchestrator.max_agents == 6

        # Successfully prune active advisors if new max_agents is lower
        orchestrator._load_predefined_advisors()
        assert len(orchestrator.advisors) > 2
        res = handle_set_max_agents_command(orchestrator, "2")
        assert res
        assert orchestrator.max_agents == 2
        assert len(orchestrator.advisors) == 2

        # Rejects non-integers without modifying max_agents
        res = handle_set_max_agents_command(orchestrator, "six")
        assert not res
        assert orchestrator.max_agents == 2

        res = handle_set_max_agents_command(orchestrator, "2.5")
        assert not res
        assert orchestrator.max_agents == 2

    def test_handle_set_round_tables_command(self):
        """Verify setting deliberation rounds on current thread."""
        orchestrator = BoardOrchestrator()
        assert orchestrator.max_rounds == 3

        # Successfully set max_rounds
        res = handle_set_round_tables_command(orchestrator, "5")
        assert res
        assert orchestrator.max_rounds == 5

        # Rejects non-integers without modifying max_rounds
        res = handle_set_round_tables_command(orchestrator, "invalid")
        assert not res
        assert orchestrator.max_rounds == 5

        res = handle_set_round_tables_command(orchestrator, "0")
        assert not res
        assert orchestrator.max_rounds == 5

    def test_new_thread_resets_max_agents_and_rounds_to_defaults(self):
        """Verify that per-thread settings (max_agents, max_rounds) reset to defaults for a new thread."""
        orchestrator = BoardOrchestrator()
        orchestrator.max_agents = 4
        orchestrator.max_rounds = 5

        old_session_id = orchestrator.session_id
        new_session_id = orchestrator.reset_session()

        assert new_session_id != old_session_id
        # Must reset to default value of 10 and 3
        assert orchestrator.max_agents == 10
        assert orchestrator.max_rounds == 3


class TestSessionPersistence:
    """Tests for session JSON persistence, listing, and lifecycle."""

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

        assert test_file.exists()

        # Check listing
        sessions = orchestrator.list_saved_sessions()
        session_ids = [s["session_id"] for s in sessions]
        assert test_session_id in session_ids

        # Check loading
        loaded = orchestrator.load_session_by_id(test_session_id)
        assert loaded
        assert orchestrator.current_problem == "Should we pivot from B2C to B2B SaaS?"
        assert len(orchestrator.advisors) == 1
        assert orchestrator.advisors[0].name == "Marcus Vance"
        assert len(orchestrator.messages) == 2
        assert orchestrator.final_plan == "Pivot conditionally within 90 days."

        # Check deletion
        deleted = orchestrator.delete_session_by_id(test_session_id)
        assert deleted
        assert not test_file.exists()

        sessions_after = orchestrator.list_saved_sessions()
        ids_after = [s["session_id"] for s in sessions_after]
        assert test_session_id not in ids_after

    def test_orchestrator_clear_session_preserves_session_id(self):
        """Verify clear_session clears advisors, problem, messages, and plan in the SAME session without changing session_id."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        orchestrator.current_problem = "Existing strategic dilemma"
        orchestrator.final_plan = "Existing action plan"
        original_session_id = orchestrator.session_id

        returned_id = orchestrator.clear_session()
        assert returned_id == original_session_id
        assert orchestrator.session_id == original_session_id
        assert orchestrator.current_problem == ""
        assert orchestrator.final_plan == ""
        assert orchestrator.advisors == []
        assert orchestrator.messages == []

    def test_handle_cls_command(self):
        """Verify /cls command clears session state and resets slate without generating a new session."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        orchestrator.current_problem = "Some dilemma"
        original_id = orchestrator.session_id

        with patch("rich.console.Console.clear"):
            handle_cls_command(orchestrator)

        assert orchestrator.session_id == original_id
        assert orchestrator.current_problem == ""
        assert orchestrator.advisors == []
        assert orchestrator.final_plan == ""

    async def test_session_model_and_effort_persistence(self):
        """Verify session JSON saves and restores custom model and effort settings."""
        orchestrator = BoardOrchestrator(model="custom-exp-model", effort="high")
        test_session_id = f"test_meta_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        test_file = SESSIONS_DIR / f"session_{test_session_id}.json"

        orchestrator.session_id = test_session_id
        orchestrator._load_predefined_advisors()
        orchestrator._save_session_memories("Test dilemma", "Test plan")

        assert test_file.exists()
        with open(test_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("model") == "custom-exp-model"
        assert data.get("effort") == "high"

        # Now load with a new orchestrator and verify model/effort are restored
        new_orchestrator = BoardOrchestrator()
        new_orchestrator.load_session_by_id(test_session_id)
        assert new_orchestrator.model == "custom-exp-model"
        assert new_orchestrator.effort == "high"
        assert new_orchestrator.synthesizer_invoker.model == "custom-exp-model"
        assert new_orchestrator.synthesizer_invoker.effort == "high"

        test_file.unlink(missing_ok=True)


class TestAsyncCommandFlows:
    """Tests for asynchronous user command interactions and deliberation."""

    async def test_handle_slash_trigger_shows_options_menu(self):
        """Verify giving '/' displays the options menu and executes selected option."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        orchestrator.final_plan = "Mock Action Plan"

        # User gives '/' -> menu shown -> selects '6' (/plan)
        with patch("rich.prompt.Prompt.ask", return_value="6"), \
             patch("main.render_plan") as mock_render_plan:
            res = await handle_slash_trigger(orchestrator)
            assert res
            mock_render_plan.assert_called_once_with("Mock Action Plan")

    async def test_handle_slash_trigger_numeric_help(self):
        """Verify selecting '8' in slash menu shows help."""
        orchestrator = BoardOrchestrator()
        with patch("rich.prompt.Prompt.ask", return_value="8"), \
             patch("main.show_help") as mock_help:
            res = await handle_slash_trigger(orchestrator)
            assert res
            mock_help.assert_called_once()

    async def test_handle_slash_trigger_cancel(self):
        """Verify pressing Enter in slash menu cancels cleanly."""
        orchestrator = BoardOrchestrator()
        with patch("rich.prompt.Prompt.ask", return_value=""):
            res = await handle_slash_trigger(orchestrator)
            assert not res

    async def test_handle_slash_trigger_chained_input_rejected(self):
        """Verify chained input in slash options prompt is blocked."""
        orchestrator = BoardOrchestrator()
        with patch("rich.prompt.Prompt.ask", return_value="/new /history"):
            res = await handle_slash_trigger(orchestrator)
            assert not res

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

        assert target_idx is not None

        prompt_inputs = [f"d {target_idx}", "y", ""]
        with patch("rich.prompt.Prompt.ask", side_effect=prompt_inputs):
            res = await handle_history_command(orchestrator)
            assert not res

        assert not test_file.exists()

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

        assert target_idx is not None

        with patch("rich.prompt.Prompt.ask", return_value=str(target_idx)):
            res = await handle_history_command(orchestrator)
            assert res
            assert orchestrator.session_id == test_session_id
            assert orchestrator.current_problem == "Test Problem to Load"

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

        assert not test_file.exists()

    async def test_handle_new_command_resets_session(self):
        """Verify /new resets session and triggers fresh deliberation."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        orchestrator.current_problem = "Old problem"
        old_session_id = orchestrator.session_id

        with patch("main.run_problem_session", new_callable=AsyncMock) as mock_run:
            await handle_new_command(orchestrator, "Brand new startup dilemma")
            mock_run.assert_awaited_once_with(orchestrator, "Brand new startup dilemma")

        assert orchestrator.session_id != old_session_id
        assert orchestrator.current_problem == ""
        assert orchestrator.advisors == []

    async def test_ask_input_async_execution_no_warnings(self):
        """Verify ask_input executes cleanly as an awaited coroutine in active asyncio loop without RuntimeWarning."""
        with warnings.catch_warnings(record=True) as w, \
             patch("rich.prompt.Prompt.ask", return_value="test input"):
            res = await ask_input("Prompt Rich", "<b>Prompt HTML</b>")
            assert res == "test input"
            runtime_warnings = [item for item in w if issubclass(item.category, RuntimeWarning)]
            assert len(runtime_warnings) == 0

    async def test_evaluate_user_input_need_no_indicators_skips_llm(self):
        """Verify that plain statements without questions or user/constraint indicators skip LLM reading."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        advisor = orchestrator.advisors[0]
        statement = "We should focus on organic growth and improving gross margins this quarter."

        with patch.object(orchestrator.synthesizer_invoker, "invoke_async", new_callable=AsyncMock) as mock_invoke:
            result = await orchestrator.evaluate_user_input_need(advisor, statement, "Test dilemma")
            mock_invoke.assert_not_called()
            assert result is None

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
            assert result is None

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
            assert result is None

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
            assert result == "What is your net monthly burn rate?"

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
            assert result == "What is your personal timeline and preferred horizon for an exit?"

    async def test_evaluate_user_input_need_fallback_on_invoker_failure(self):
        """Verify safe fallback when invoker raises an unexpected error."""
        orchestrator = BoardOrchestrator()
        orchestrator._load_predefined_advisors()
        advisor = orchestrator.advisors[0]

        # Case A: Casual mention with exception -> defaults to None (no false interruption)
        statement_casual = "As @User said earlier, we should proceed carefully."
        with patch.object(orchestrator.synthesizer_invoker, "invoke_async", side_effect=RuntimeError("CLI failure")):
            res_casual = await orchestrator.evaluate_user_input_need(advisor, statement_casual, "Test dilemma")
            assert res_casual is None

        # Case B: Explicit @User question with question mark -> falls back to question extraction
        statement_direct = "@User, can you confirm if the budget is under $50k?"
        with patch.object(orchestrator.synthesizer_invoker, "invoke_async", side_effect=RuntimeError("CLI failure")):
            res_direct = await orchestrator.evaluate_user_input_need(advisor, statement_direct, "Test dilemma")
            assert res_direct is not None
            assert "@User" in res_direct

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
        assert plan == "Action Plan"
        assert user_input_called

        # Check recorded messages to verify user input was incorporated
        user_msgs = [m for m in orchestrator.messages if m.sender == "USER" and m.stage == "round_1_user_input"]
        assert len(user_msgs) == 1
        assert "10k/month" in user_msgs[0].content


class TestEnhancedFeaturesAndEdgeCases:
    """Tests for edge cases, dynamic advisor limits, chaining prevention with set commands, and UI badges."""

    def test_command_chaining_catches_set_commands(self):
        """Verify command chaining catches compound set-max-agents and set-round-tables commands."""
        is_chained, err = check_command_chaining("/cls set-max-agents")
        assert is_chained is True
        assert "set-max-agents" in err

        is_chained, err = check_command_chaining("/history set-round-tables")
        assert is_chained is True
        assert "set-round-tables" in err

        is_chained, err = check_command_chaining("/advisors max-agents")
        assert is_chained is True

    def test_parse_advisors_json_supports_custom_max_agents(self):
        """Verify parse_advisors_json respects max_advisors parameter up to 20."""
        from board.advisor_builder import parse_advisors_json

        advisors_data = [
            {"id": f"adv_{i}", "name": f"Advisor {i}", "role": f"Role {i}", "persona": "P"}
            for i in range(16)
        ]
        raw_json = json.dumps(advisors_data)

        # Default max is 10
        parsed_default = parse_advisors_json(raw_json)
        assert len(parsed_default) == 10

        # Custom max allows up to requested count
        parsed_15 = parse_advisors_json(raw_json, max_advisors=15)
        assert len(parsed_15) == 15
        assert parsed_15[14]["id"] == "adv_14"

    def test_render_message_dynamic_round_badges_and_system(self):
        """Verify render_message dynamically labels round badges and handles SYSTEM messages cleanly."""
        from board.advisor import Advisor
        from board.orchestrator import BoardMessage
        from board.cli_ui import render_message

        advisor = Advisor(
            advisor_id="test_adv",
            name="Test Advisor",
            tag="@TestAdv",
            role="Specialist",
            persona="Pragmatic",
        )
        advisor_map = {"@testadv": advisor}

        # 1. Round 2 final deliberation (when max_rounds=2)
        msg_round2_final = BoardMessage("Test Advisor", "@TestAdv", "Final verdict.", stage="round_2_final")
        render_message(msg_round2_final, advisor_map)

        # 2. Round 5 final deliberation (when max_rounds=5)
        msg_round5_final = BoardMessage("Test Advisor", "@TestAdv", "Final verdict 5.", stage="round_5_final")
        render_message(msg_round5_final, advisor_map)

        # 3. Round 4 cross-examination debate
        msg_round4_debate = BoardMessage("Test Advisor", "@TestAdv", "Debate point.", stage="round_4_debate")
        render_message(msg_round4_debate, advisor_map)

        # 4. System message
        msg_system = BoardMessage("SYSTEM", "@System", "Pivoting in session to new problem.", stage="session_suspended_pivot")
        render_message(msg_system, advisor_map)
