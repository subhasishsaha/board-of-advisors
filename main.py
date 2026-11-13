import argparse
import asyncio
import re
import sys
from pathlib import Path
from typing import Optional, Tuple
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich import box
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML

from board.config import DEFAULT_MODEL, DEFAULT_EFFORT
from board.cli_ui import (
    console,
    render_banner,
    render_advisors_table,
    render_sessions_history_table,
    render_message,
    render_plan,
    render_slash_menu,
    highlight_tags,
)
from board.orchestrator import BoardOrchestrator, BoardMessage
from board.advisor import Advisor
from board.cli_completer import (
    BoardSlashCompleter,
    get_interactive_prompt_session,
)

# Global status tracker for clean suspension and resumption
_active_status = None
_prompt_session: Optional[PromptSession] = None

async def ask_input(
    prompt_rich: str,
    prompt_html: str,
    default: str = "",
) -> str:
    """
    Prompts the user asynchronously. If an interactive TTY is available,
    uses prompt_toolkit.prompt_async() for live dropdown completion on '/'
    (matching Claude Code & Antigravity) without blocking the asyncio loop.
    Otherwise, gracefully falls back to rich.prompt.Prompt.ask().
    """
    global _prompt_session
    if _prompt_session is not None and sys.stdin.isatty():
        try:
            val = await _prompt_session.prompt_async(HTML(prompt_html), default=default)
            return val.strip()
        except (KeyboardInterrupt, EOFError):
            raise
        except Exception:
            pass
    return Prompt.ask(prompt_rich, default=default).strip()

def check_command_chaining(raw_input: str) -> Tuple[bool, Optional[str]]:
    """
    Detects and prevents chaining of slash commands.
    Returns (is_chained, error_message).
    """
    text = raw_input.strip()
    if not text:
        return False, None

    # Check 1: Multiple leading slashes e.g. '//new', '///help'
    if text.startswith("//"):
        return True, "Multiple consecutive slashes detected ('//'). Please run a single command using '/'."

    # Check 2: Compound chaining operators e.g. '/history && /new', '/plan ; /advisors', '/new & /cls'
    chain_separators = [r"&&", r"\|\|", r";", r"\|", r"&"]
    for sep in chain_separators:
        sep_clean = sep.replace("\\", "")
        if re.search(r"\s*" + sep + r"\s*/", text) or (text.startswith("/") and re.search(r"\s+" + sep + r"\s+", text)):
            return True, f"Command chaining with separator '{sep_clean}' is not allowed. Please run one command at a time."

    # Check 3: Concatenated slash commands without spaces e.g. '/history/new' or '/plan/advisors'
    if re.match(r"^/\w+/\w+", text):
        return True, f"Chained slash commands detected ('{text.split()[0]}'). Please run one command at a time."

    # Check 4: Multiple slash tokens or command keywords e.g. '/history /new', '/delete 1 /plan', '/new /cls'
    if text.startswith("/"):
        tokens = text.split()
        if len(tokens) > 1:
            # Check if any subsequent token begins with '/'
            subsequent_slash_tokens = [tok for tok in tokens[1:] if tok.startswith("/")]
            if subsequent_slash_tokens:
                chained_example = f"{tokens[0]} {subsequent_slash_tokens[0]}"
                return True, f"Command chaining is not allowed ('{chained_example}'). Please run one command at a time."

            # Check if any subsequent token is a known command keyword
            known_command_names = {
                "new", "history", "hist", "cls", "clear", "advisors", "advisor",
                "plan", "memory", "memories", "help", "exit", "quit", "delete", "del", "rm"
            }
            first_cmd = tokens[0].lstrip("/").lower()
            if first_cmd in ("history", "advisors", "advisor", "plan", "memory", "memories", "help", "exit", "quit", "cls", "clear"):
                if tokens[1].lower() in known_command_names:
                    return True, f"Command chaining is not allowed ('{tokens[0]} {tokens[1]}'). Please run one command at a time."
            elif first_cmd in ("delete", "del", "rm"):
                if len(tokens) > 2 and tokens[2].lower() in known_command_names:
                    return True, f"Command chaining is not allowed ('{tokens[0]} {tokens[1]} {tokens[2]}'). Please run one command at a time."

    return False, None

def parse_command(user_input: str) -> Tuple[Optional[str], str]:
    """
    Parses user input to determine if it is a slash command or keyword command.
    Returns (cmd_name, cmd_arg) or (None, user_input).
    """
    text = user_input.strip()
    if not text:
        return None, ""

    # Direct slash trigger to open options menu
    if text in ("/", "/?", "/menu", "/options"):
        return "slash", ""

    is_slash = text.startswith("/")
    cleaned = text[1:].strip() if is_slash else text

    parts = cleaned.split(maxsplit=1)
    keyword = parts[0].lower() if parts else ""
    arg = parts[1].strip() if len(parts) > 1 else ""

    known_commands = {
        "new", "history", "hist", "cls", "clear", "advisors", "advisor",
        "plan", "memory", "memories", "help", "?", "exit", "quit",
        "delete", "del", "rm", "slash", "menu", "options"
    }

    if is_slash or keyword in known_commands:
        return keyword, arg

    return None, text

def show_help():
    console.print("""
[bold cyan]Available Commands:[/bold cyan]
  [yellow]/[/yellow]                     - Show the interactive Slash Command menu
  [yellow]/new [problem][/yellow]       - Create a brand new session with a fresh tailored board
  [yellow]/history[/yellow]             - Browse previous sessions to load or delete ('d #')
  [yellow]/delete <#>[/yellow]          - Delete a specific saved session by index or ID
  [yellow]/cls[/yellow]                 - Clear current session slate without starting a new session
  [yellow]/advisors[/yellow]            - Show active board members and their tags
  [yellow]/plan[/yellow]                - Review the consolidated Plan of Action
  [yellow]/memory[/yellow]              - View what advisors have stored in persistent memory
  [yellow]/help[/yellow]                - Show this help message
  [yellow]/exit[/yellow]                - Exit the session
""", style="white")

def show_memories(orchestrator: BoardOrchestrator):
    console.print("\n[bold cyan]🧠 Persistent Advisor Memories:[/bold cyan]")
    if not orchestrator.advisors:
        console.print("[dim]No active advisors yet.[/dim]\n")
        return
    for adv in orchestrator.advisors:
        mem_text = adv.memory.format_memory_for_prompt()
        console.print(f"\n[bold {adv.color}]{adv.avatar} {adv.name} ({adv.tag}) Memory:[/bold {adv.color}]")
        console.print(mem_text, style="dim")
    console.print()

async def handle_slash_trigger(orchestrator: BoardOrchestrator) -> bool:
    """
    Triggered when the user enters '/' to display all available slash commands
    and prompts for instant numeric (1-9) or command selection.
    """
    render_slash_menu(
        has_board=bool(orchestrator.advisors),
        has_plan=bool(orchestrator.final_plan),
    )
    selection = await ask_input(
        "[bold yellow]Select an option [1-9], type a command, or press Enter to return[/bold yellow]",
        "<b><ansiyellow>Select an option [1-9], type a command, or press Enter to return</ansiyellow></b> &gt; ",
    )

    if not selection:
        console.print("[dim]Returned to prompt.[/dim]\n")
        return False

    # Prevent chaining in the options prompt
    is_chained, chain_err = check_command_chaining(selection)
    if is_chained:
        console.print(f"\n[bold red]⛔ {chain_err}[/bold red]\n")
        return False

    num_map = {
        "1": "new",
        "2": "history",
        "3": "delete",
        "4": "cls",
        "5": "advisors",
        "6": "plan",
        "7": "memory",
        "8": "help",
        "9": "exit",
    }

    if selection in num_map:
        cmd = num_map[selection]
        arg = ""
    else:
        cmd, arg = parse_command(selection)

    if cmd is None:
        console.print(f"[red]Invalid selection: '{selection}'. Type / for available options.[/red]\n")
        return False

    if cmd in ("exit", "quit"):
        console.print("[bold green]Thank you for consulting your Board of Advisors. Good luck with your execution![/bold green]")
        sys.exit(0)
    elif cmd in ("help", "?"):
        show_help()
    elif cmd in ("history", "hist"):
        await handle_history_command(orchestrator)
    elif cmd in ("delete", "del", "rm"):
        await handle_delete_command(orchestrator, arg)
    elif cmd == "new":
        await handle_new_command(orchestrator, arg)
    elif cmd in ("cls", "clear"):
        handle_cls_command(orchestrator)
    elif cmd in ("advisors", "advisor"):
        if orchestrator.advisors:
            render_advisors_table(orchestrator.advisors)
        else:
            console.print("[dim]No active board assembled yet. Enter a problem or load a past session with /history.[/dim]\n")
    elif cmd == "plan":
        if orchestrator.final_plan:
            render_plan(orchestrator.final_plan)
        else:
            console.print("[dim]No plan generated yet.[/dim]\n")
    elif cmd in ("memory", "memories"):
        show_memories(orchestrator)
    elif cmd in ("slash", "menu", "options"):
        return await handle_slash_trigger(orchestrator)
    else:
        console.print(f"[red]Unknown command: /{cmd}. Type / for available options.[/red]\n")

    return True

async def ask_user_callback(advisor: Advisor, question: str) -> str:
    """
    Suspends the round table deliberation and prompts the user when an advisor
    specifically requests user input or opinion.
    """
    global _active_status
    if _active_status:
        _active_status.stop()

    console.print(
        f"\n[bold yellow]⏸️ Deliberation Suspended:[/bold yellow] "
        f"[bold {advisor.color}]{advisor.avatar} {advisor.name} ({advisor.tag})[/bold {advisor.color}] "
        f"is asking for your direct input!\n"
    )

    prompt_panel = Panel(
        highlight_tags(question),
        title=f"❓ Direct Inquiry from {advisor.name}",
        title_align="left",
        border_style="bright_yellow",
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print(prompt_panel)
    console.print()

    user_answer = await ask_input(
        "[bold blue]Your Answer / Input[/bold blue]",
        "<b><ansiblue>Your Answer / Input</ansiblue></b> &gt; ",
    )
    console.print("\n[dim]▶️ Input received. Resuming round table deliberation...[/dim]\n")

    if _active_status:
        _active_status.start()

    return user_answer

async def handle_history_command(orchestrator: BoardOrchestrator) -> bool:
    """List previous sessions and let the user select one to load, or delete."""
    while True:
        sessions = orchestrator.list_saved_sessions()
        if not sessions:
            console.print("[dim]No previous saved sessions found in storage/sessions/.[/dim]\n")
            return False

        render_sessions_history_table(sessions)
        choice = await ask_input(
            "[bold yellow]Select a session # to load, 'd #' to delete, or press Enter to return[/bold yellow]",
            "<b><ansiyellow>Select a session # to load, 'd #' to delete, or press Enter to return</ansiyellow></b> &gt; ",
        )

        if not choice:
            console.print("[dim]History browser closed.[/dim]\n")
            return False

        choice_lower = choice.lower()
        if choice_lower in ("q", "quit", "exit", "cancel", "back"):
            console.print("[dim]History browser closed.[/dim]\n")
            return False

        # Prevent chained delete commands
        is_chained, chain_err = check_command_chaining(choice)
        if is_chained:
            console.print(f"\n[bold red]⛔ {chain_err}[/bold red]\n")
            continue

        # Check for delete syntax: 'd 2', 'del 2', 'delete 2', 'rm 2', 'd2'
        del_match = re.match(r"^(?:d|del|delete|rm)\s*(\d+)$", choice_lower)
        if del_match:
            del_idx = int(del_match.group(1))
            if 1 <= del_idx <= len(sessions):
                target = sessions[del_idx - 1]
                confirm = (await ask_input(
                    f"[bold red]Are you sure you want to delete session #{del_idx} ({target['session_id']})? [y/N][/bold red]",
                    f"<b><ansired>Are you sure you want to delete session #{del_idx} ({target['session_id']})? [y/N]</ansired></b> &gt; ",
                    default="n",
                )).lower()
                if confirm in ("y", "yes"):
                    if orchestrator.delete_session_by_id(target["session_id"]):
                        console.print(f"[bold green]🗑️ Session #{del_idx} ({target['session_id']}) deleted successfully.[/bold green]\n")
                    else:
                        console.print("[bold red]Failed to delete session.[/bold red]\n")
                else:
                    console.print("[dim]Deletion cancelled.[/dim]\n")
                continue
            else:
                console.print(f"[red]Invalid session number #{del_idx}. Valid range: 1 to {len(sessions)}[/red]\n")
                continue

        # Check for numeric selection to load
        if choice.isdigit():
            load_idx = int(choice)
            if 1 <= load_idx <= len(sessions):
                target = sessions[load_idx - 1]
                success = orchestrator.load_session_by_id(target["session_id"])
                if success:
                    console.print(f"\n[bold green]✅ Loaded session {target['session_id']} successfully![/bold green]\n")
                    console.print(f"[bold white]Problem Context:[/bold white] {orchestrator.current_problem}\n")
                    render_advisors_table(orchestrator.advisors)
                    if orchestrator.final_plan:
                        render_plan(orchestrator.final_plan)
                    console.print("\n[bold cyan]Resumed interactive discussion with this board. You can ask follow-ups, tag advisors, or use /cls to clear.[/bold cyan]\n")
                    return True
                else:
                    console.print("[bold red]Failed to load selected session.[/bold red]\n")
                    return False
            else:
                console.print(f"[red]Invalid session number #{load_idx}. Valid range: 1 to {len(sessions)}[/red]\n")
                continue

        console.print("[red]Invalid input. Enter a session number, 'd <#>' to delete, or press Enter to return.[/red]\n")

async def handle_delete_command(orchestrator: BoardOrchestrator, arg: str):
    """Direct deletion command for /delete <#> or /delete <id>."""
    sessions = orchestrator.list_saved_sessions()
    if not sessions:
        console.print("[dim]No saved sessions found in storage/sessions/.[/dim]\n")
        return

    target_session = None
    target_idx = None
    target_id = None

    if arg:
        is_chained, chain_err = check_command_chaining(f"/delete {arg}")
        if is_chained:
            console.print(f"\n[bold red]⛔ {chain_err}[/bold red]\n")
            return
        arg_clean = arg.strip().lstrip("#")
        if arg_clean.isdigit():
            target_idx = int(arg_clean)
        else:
            target_id = arg_clean
    else:
        render_sessions_history_table(sessions)
        choice = await ask_input(
            "[bold yellow]Enter session # to delete (or Enter to cancel)[/bold yellow]",
            "<b><ansiyellow>Enter session # to delete (or Enter to cancel)</ansiyellow></b> &gt; ",
        )
        if not choice:
            console.print("[dim]Deletion cancelled.[/dim]\n")
            return
        choice_clean = choice.lstrip("#")
        if choice_clean.isdigit():
            target_idx = int(choice_clean)
        else:
            target_id = choice_clean

    if target_idx is not None:
        if 1 <= target_idx <= len(sessions):
            target_session = sessions[target_idx - 1]
        else:
            console.print(f"[red]Invalid session index #{target_idx}. Valid range: 1 to {len(sessions)}[/red]\n")
            return
    elif target_id:
        for s in sessions:
            if s["session_id"] == target_id or s["session_id"].endswith(target_id):
                target_session = s
                break
        if not target_session:
            console.print(f"[red]No session found with ID matching '{target_id}'.[/red]\n")
            return

    confirm = (await ask_input(
        f"[bold red]Are you sure you want to delete session {target_session['session_id']}? [y/N][/bold red]",
        f"<b><ansired>Are you sure you want to delete session {target_session['session_id']}? [y/N]</ansired></b> &gt; ",
        default="n",
    )).lower()
    if confirm in ("y", "yes"):
        if orchestrator.delete_session_by_id(target_session["session_id"]):
            console.print(f"[bold green]🗑️ Session {target_session['session_id']} deleted successfully.[/bold green]\n")
        else:
            console.print("[bold red]Failed to delete session.[/bold red]\n")
    else:
        console.print("[dim]Deletion cancelled.[/dim]\n")

def parse_args():
    parser = argparse.ArgumentParser(
        description="Executive Board of Advisors - Autonomous Multi-Agent Decision Council",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default=DEFAULT_MODEL,
        help="Model identifier to use with agy CLI (e.g. 'gemini-3.8-flash-medium', 'gemini-2.5-pro')",
    )
    parser.add_argument(
        "-e", "--effort",
        type=str,
        default=DEFAULT_EFFORT,
        help="Reasoning effort level to use with agy CLI (e.g. 'low', 'medium', 'high')",
    )
    return parser.parse_args()

def handle_cls_command(orchestrator: BoardOrchestrator):
    """
    Clears the current session state (problem, advisors, debate transcript, and plan)
    in the SAME session without starting a new session, and clears the terminal screen.
    """
    session_id = orchestrator.clear_session()
    console.clear()
    render_banner()
    console.print(
        f"[dim]Backend: agy CLI detached mode  |  Model: [bold cyan]{orchestrator.model}[/bold cyan]  |  Effort: [bold cyan]{orchestrator.effort}[/bold cyan][/dim]\n"
    )
    console.print(f"[bold green]🧹 Current session cleared (Session: {session_id}).[/bold green]")
    console.print("[dim]The session slate is reset. You can now describe a new dilemma or load history.[/dim]\n")

async def handle_new_command(orchestrator: BoardOrchestrator, arg: str = ""):
    """Starts a completely new session with a new problem and fresh bespoke board."""
    new_problem = arg.strip()
    if new_problem:
        is_chained, chain_err = check_command_chaining(f"/new {new_problem}")
        if is_chained:
            console.print(f"\n[bold red]⛔ {chain_err}[/bold red]\n")
            return

    console.print("\n[bold yellow]🆕 Starting a brand new session...[/bold yellow]")
    if not new_problem:
        new_problem = await ask_input(
            "[bold green]Enter your problem for the new session (or / for options)[/bold green]",
            "<b><ansigreen>Enter your problem for the new session (or / for options)</ansigreen></b> &gt; ",
        )
        if not new_problem:
            console.print("[dim]New session cancelled.[/dim]\n")
            return
        if new_problem in ("/", "/?", "/menu", "/options"):
            await handle_slash_trigger(orchestrator)
            return
        is_chained, chain_err = check_command_chaining(new_problem)
        if is_chained:
            console.print(f"\n[bold red]⛔ {chain_err}[/bold red]\n")
            return

    orchestrator.reset_session()
    await run_problem_session(orchestrator, new_problem)

async def run_problem_session(orchestrator: BoardOrchestrator, problem: str):
    """Dynamically assemble board and run deliberation for a given problem."""
    global _active_status

    # 1. Dynamic Advisor Generation
    with console.status("[bold cyan]🔍 Analyzing decision problem and assembling bespoke Board of Advisors...[/bold cyan]", spinner="dots"):
        advisors = await orchestrator.build_dynamic_advisors(problem)

    console.print(f"\n[bold green]🏛️ Successfully assembled a bespoke board of {len(advisors)} advisors tailored to your problem (Session: {orchestrator.session_id}):[/bold green]\n")
    render_advisors_table(advisors)

    # 2. Multi-Stage Deliberation (at most 3 rounds with mid-session user input support)
    _active_status = console.status("[bold cyan]🏛️ The Board of Advisors is deliberating (max 3 rounds)...[/bold cyan]", spinner="dots")
    _active_status.start()
    try:
        plan = await orchestrator.run_deliberation(problem=problem)
    finally:
        _active_status.stop()
        _active_status = None

    console.print("\n[bold green]✅ Deliberation concluded and Action Plan synthesized![/bold green]\n")
    render_plan(plan)

async def main(model: Optional[str] = None, effort: Optional[str] = None):
    global _prompt_session
    if model is None or effort is None:
        args = parse_args()
        model = model or args.model
        effort = effort or args.effort

    render_banner()
    console.print(
        f"[dim]Backend: agy CLI detached mode  |  Model: [bold cyan]{model}[/bold cyan]  |  Effort: [bold cyan]{effort}[/bold cyan][/dim]\n"
    )

    orchestrator = None

    def on_message(msg: BoardMessage):
        if orchestrator:
            render_message(msg, orchestrator.advisors_by_tag)

    try:
        orchestrator = BoardOrchestrator(
            on_message_callback=on_message,
            user_input_callback=ask_user_callback,
            model=model,
            effort=effort,
        )
    except Exception as e:
        console.print(f"[bold red]Initialization Error:[/bold red] {e}")
        sys.exit(1)

    _prompt_session = get_interactive_prompt_session(
        get_advisors_fn=lambda: orchestrator.advisors if orchestrator else []
    )

    console.print("[bold yellow]Describe your strategic dilemma, or type / to see available options:[/bold yellow]\n")

    while True:
        if not orchestrator.current_problem:
            prompt_rich = "[bold green]Your Dilemma (type / for options)[/bold green]"
            prompt_html = "<b><ansigreen>Your Dilemma (type / for options)</ansigreen></b> &gt; "
        else:
            prompt_rich = "[bold blue]You (type / for options)[/bold blue]"
            prompt_html = "<b><ansiblue>You (type / for options)</ansiblue></b> &gt; "

        try:
            raw_input = await ask_input(prompt_rich, prompt_html)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session terminated.[/dim]")
            break

        if not raw_input:
            continue

        # 1. Check for command chaining and prevent it
        is_chained, chain_err = check_command_chaining(raw_input)
        if is_chained:
            console.print(f"\n[bold red]⛔ {chain_err}[/bold red]\n")
            continue

        # 2. Check for single slash trigger to show options menu
        if raw_input in ("/", "/?", "/menu", "/options", "slash"):
            await handle_slash_trigger(orchestrator)
            continue

        cmd, arg = parse_command(raw_input)

        if cmd is not None:
            if cmd in ("exit", "quit"):
                console.print("[bold green]Thank you for consulting your Board of Advisors. Good luck with your execution![/bold green]")
                break
            elif cmd in ("slash", "menu", "options"):
                await handle_slash_trigger(orchestrator)
            elif cmd in ("help", "?"):
                show_help()
            elif cmd in ("history", "hist"):
                await handle_history_command(orchestrator)
            elif cmd in ("delete", "del", "rm"):
                await handle_delete_command(orchestrator, arg)
            elif cmd == "new":
                await handle_new_command(orchestrator, arg)
            elif cmd in ("cls", "clear"):
                handle_cls_command(orchestrator)
            elif cmd in ("advisors", "advisor"):
                if orchestrator.advisors:
                    render_advisors_table(orchestrator.advisors)
                else:
                    console.print("[dim]No active board assembled yet. Enter a problem or load a past session with /history.[/dim]\n")
            elif cmd == "plan":
                if orchestrator.final_plan:
                    render_plan(orchestrator.final_plan)
                else:
                    console.print("[dim]No plan generated yet.[/dim]\n")
            elif cmd in ("memory", "memories"):
                show_memories(orchestrator)
            else:
                console.print(f"[red]Unknown command: /{cmd}.[/red]\n")
                render_slash_menu(has_board=bool(orchestrator.advisors), has_plan=bool(orchestrator.final_plan))
            continue

        # If it wasn't a command, it's either the initial problem or a follow-up
        if not orchestrator.current_problem:
            # First problem!
            await run_problem_session(orchestrator, raw_input)
            console.print("\n[bold cyan]💬 The board is now open for follow-up questions and discussion.[/bold cyan]")
            console.print("[dim]Commands: type / for options menu, /cls to clear session, /new for fresh session, /plan[/dim]\n")
        else:
            # Active deliberation follow-up
            with console.status("[bold cyan]Advisors are reviewing your follow-up...[/bold cyan]", spinner="dots"):
                await orchestrator.handle_user_followup(raw_input)

if __name__ == "__main__":
    asyncio.run(main())
