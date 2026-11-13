import asyncio
import re
import sys
from pathlib import Path
from typing import Optional, Tuple
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich import box

from board.config import DEFAULT_MODEL, DEFAULT_EFFORT
from board.cli_ui import (
    console,
    render_banner,
    render_advisors_table,
    render_sessions_history_table,
    render_message,
    render_plan,
    highlight_tags,
)
from board.orchestrator import BoardOrchestrator, BoardMessage
from board.advisor import Advisor

# Global status tracker for clean suspension and resumption
_active_status = None

def parse_command(user_input: str) -> Tuple[Optional[str], str]:
    """
    Parses user input to determine if it is a slash command or keyword command.
    Returns (cmd_name, cmd_arg) or (None, user_input).
    """
    text = user_input.strip()
    if not text:
        return None, ""

    is_slash = text.startswith("/")
    cleaned = text[1:].strip() if is_slash else text

    parts = cleaned.split(maxsplit=1)
    keyword = parts[0].lower() if parts else ""
    arg = parts[1].strip() if len(parts) > 1 else ""

    known_commands = {
        "new", "history", "hist", "suspend", "advisors", "advisor",
        "plan", "memory", "memories", "help", "?", "exit", "quit",
        "delete", "del", "rm"
    }

    if is_slash or keyword in known_commands:
        return keyword, arg

    return None, text

def show_help():
    console.print("""
[bold cyan]Available Commands:[/bold cyan]
  [yellow]/new [problem][/yellow]       - Create a brand new session with a fresh tailored board
  [yellow]/history[/yellow]             - Browse previous sessions to load or delete ('d #')
  [yellow]/delete <#>[/yellow]          - Delete a specific saved session by index or ID
  [yellow]/suspend [pivot][/yellow]    - Suspend current deliberation in the SAME session and enter a new problem
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

    user_answer = Prompt.ask("[bold blue]Your Answer / Input[/bold blue]").strip()
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
        choice = Prompt.ask(
            "[bold yellow]Select a session # to load, 'd #' to delete, or press Enter to return[/bold yellow]",
            default="",
        ).strip()

        if not choice:
            console.print("[dim]History browser closed.[/dim]\n")
            return False

        choice_lower = choice.lower()
        if choice_lower in ("q", "quit", "exit", "cancel", "back"):
            console.print("[dim]History browser closed.[/dim]\n")
            return False

        # Check for delete syntax: 'd 2', 'del 2', 'delete 2', 'rm 2', 'd2'
        del_match = re.match(r"^(?:d|del|delete|rm)\s*(\d+)$", choice_lower)
        if del_match:
            del_idx = int(del_match.group(1))
            if 1 <= del_idx <= len(sessions):
                target = sessions[del_idx - 1]
                confirm = Prompt.ask(
                    f"[bold red]Are you sure you want to delete session #{del_idx} ({target['session_id']})? [y/N][/bold red]",
                    default="n",
                ).strip().lower()
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
                    console.print("\n[bold cyan]Resumed interactive discussion with this board. You can ask follow-ups, tag advisors, or use /suspend to pivot.[/bold cyan]\n")
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
        arg_clean = arg.strip().lstrip("#")
        if arg_clean.isdigit():
            target_idx = int(arg_clean)
        else:
            target_id = arg_clean
    else:
        render_sessions_history_table(sessions)
        choice = Prompt.ask("[bold yellow]Enter session # to delete (or Enter to cancel)[/bold yellow]", default="").strip()
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

    confirm = Prompt.ask(
        f"[bold red]Are you sure you want to delete session {target_session['session_id']}? [y/N][/bold red]",
        default="n",
    ).strip().lower()
    if confirm in ("y", "yes"):
        if orchestrator.delete_session_by_id(target_session["session_id"]):
            console.print(f"[bold green]🗑️ Session {target_session['session_id']} deleted successfully.[/bold green]\n")
        else:
            console.print("[bold red]Failed to delete session.[/bold red]\n")
    else:
        console.print("[dim]Deletion cancelled.[/dim]\n")

async def handle_suspend_command(orchestrator: BoardOrchestrator, arg: str = ""):
    """
    Suspends current board deliberation in the SAME session, keeps existing advisors,
    and enters a new problem or pivot.
    """
    global _active_status
    if not orchestrator.advisors:
        console.print("[red]No active board assembled yet. First describe a problem or load a session with /history.[/red]\n")
        return

    console.print(f"\n[bold yellow]⏸️ Suspending Current Board Deliberation (Same Session: {orchestrator.session_id})[/bold yellow]")
    console.print("[dim]The board remains assembled with all its context, personas, and memory.[/dim]\n")

    new_problem = arg.strip()
    if not new_problem:
        new_problem = Prompt.ask("[bold green]Enter new problem, pivot, or sub-task for this board[/bold green]").strip()
        if not new_problem:
            console.print("[dim]Suspension cancelled. Resuming current focus.[/dim]\n")
            return

    _active_status = console.status(f"[bold cyan]🏛️ Board is deliberating on the new problem within session {orchestrator.session_id}...[/bold cyan]", spinner="dots")
    _active_status.start()
    try:
        plan = await orchestrator.suspend_and_pivot(new_problem)
    finally:
        _active_status.stop()
        _active_status = None

    console.print("\n[bold green]✅ Deliberation on new problem concluded and Action Plan synthesized![/bold green]\n")
    render_plan(plan)

async def handle_new_command(orchestrator: BoardOrchestrator, arg: str = ""):
    """Starts a completely new session with a new problem and fresh bespoke board."""
    console.print("\n[bold yellow]🆕 Starting a brand new session...[/bold yellow]")
    new_problem = arg.strip()
    if not new_problem:
        new_problem = Prompt.ask("[bold green]Enter your problem for the new session[/bold green]").strip()
        if not new_problem:
            console.print("[dim]New session cancelled.[/dim]\n")
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

async def main():
    render_banner()
    console.print(f"[dim]Backend: agy CLI detached mode  |  Model: {DEFAULT_MODEL}  |  Effort: {DEFAULT_EFFORT}[/dim]\n")

    orchestrator = None

    def on_message(msg: BoardMessage):
        if orchestrator:
            render_message(msg, orchestrator.advisors_by_tag)

    try:
        orchestrator = BoardOrchestrator(
            on_message_callback=on_message,
            user_input_callback=ask_user_callback,
        )
    except Exception as e:
        console.print(f"[bold red]Initialization Error:[/bold red] {e}")
        sys.exit(1)

    console.print("[bold yellow]Describe your strategic dilemma, or enter a command (/help, /history, /new):[/bold yellow]\n")

    while True:
        prompt_label = (
            "[bold green]Your Problem (or /command)[/bold green]"
            if not orchestrator.current_problem
            else "[bold blue]You[/bold blue]"
        )

        try:
            raw_input = Prompt.ask(prompt_label).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session terminated.[/dim]")
            break

        if not raw_input:
            continue

        cmd, arg = parse_command(raw_input)

        if cmd is not None:
            if cmd in ("exit", "quit"):
                console.print("[bold green]Thank you for consulting your Board of Advisors. Good luck with your execution![/bold green]")
                break
            elif cmd in ("help", "?"):
                show_help()
            elif cmd in ("history", "hist"):
                await handle_history_command(orchestrator)
            elif cmd in ("delete", "del", "rm"):
                await handle_delete_command(orchestrator, arg)
            elif cmd == "new":
                await handle_new_command(orchestrator, arg)
            elif cmd == "suspend":
                await handle_suspend_command(orchestrator, arg)
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
                console.print(f"[red]Unknown command: /{cmd}. Type /help for available commands.[/red]\n")
            continue

        # If it wasn't a command, it's either the initial problem or a follow-up
        if not orchestrator.current_problem:
            # First problem!
            await run_problem_session(orchestrator, raw_input)
            console.print("\n[bold cyan]💬 The board is now open for follow-up questions and discussion.[/bold cyan]")
            console.print("[dim]Commands: /suspend (pivot in same session), /new (fresh session), /history, /plan, /advisors, /help[/dim]\n")
        else:
            # Active deliberation follow-up
            with console.status("[bold cyan]Advisors are reviewing your follow-up...[/bold cyan]", spinner="dots"):
                await orchestrator.handle_user_followup(raw_input)

if __name__ == "__main__":
    asyncio.run(main())
