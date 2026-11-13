import asyncio
import sys
from pathlib import Path
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

def show_help():
    console.print("""
[bold cyan]Available Commands:[/bold cyan]
  [yellow]/new[/yellow]       - Create a brand new session with a fresh tailored board
  [yellow]/history[/yellow]   - Browse previous deliberation sessions and choose one to resume
  [yellow]/suspend[/yellow]   - Suspend current deliberation in the SAME session and enter a new problem
  [yellow]/advisors[/yellow]  - Show active board members and their tags
  [yellow]/plan[/yellow]      - Review the consolidated Plan of Action
  [yellow]/memory[/yellow]    - View what advisors have stored in persistent memory
  [yellow]/help[/yellow]      - Show this help message
  [yellow]/exit[/yellow]      - Exit the session
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

async def handle_history_command(orchestrator: BoardOrchestrator):
    """List previous sessions and let the user select one to load and resume."""
    sessions = orchestrator.list_saved_sessions()
    if not sessions:
        console.print("[dim]No previous saved sessions found in storage/sessions/.[/dim]\n")
        return

    render_sessions_history_table(sessions)
    choice = Prompt.ask(
        "[bold yellow]Select a session # to load (or press Enter to cancel)[/bold yellow]",
        default="",
    ).strip()

    if not choice:
        console.print("[dim]History selection cancelled.[/dim]\n")
        return

    try:
        idx = int(choice)
        if 1 <= idx <= len(sessions):
            target = sessions[idx - 1]
            success = orchestrator.load_session_by_id(target["session_id"])
            if success:
                console.print(f"\n[bold green]✅ Loaded session {target['session_id']} successfully![/bold green]\n")
                console.print(f"[bold white]Problem Context:[/bold white] {orchestrator.current_problem}\n")
                render_advisors_table(orchestrator.advisors)
                if orchestrator.final_plan:
                    render_plan(orchestrator.final_plan)
                console.print("\n[bold cyan]Resumed interactive discussion with this board. You can ask follow-ups, tag advisors, or use /suspend to enter a new problem.[/bold cyan]\n")
            else:
                console.print("[bold red]Failed to load selected session.[/bold red]\n")
        else:
            console.print("[red]Invalid session number.[/red]\n")
    except ValueError:
        console.print("[red]Invalid input. Expected a number.[/red]\n")

async def handle_suspend_command(orchestrator: BoardOrchestrator):
    """
    Suspends current board deliberation in the SAME session, keeps existing advisors,
    and enters a new problem or pivot.
    """
    global _active_status
    if not orchestrator.advisors:
        console.print("[red]No active board assembled yet. Use /new to start a session.[/red]\n")
        return

    console.print(f"\n[bold yellow]⏸️ Suspending Current Board Deliberation (Same Session: {orchestrator.session_id})[/bold yellow]")
    console.print("[dim]The board remains assembled with all its context, personas, and memory.[/dim]\n")

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

async def handle_new_command(orchestrator: BoardOrchestrator):
    """Starts a completely new session with a new problem and fresh bespoke board."""
    console.print("\n[bold yellow]🆕 Starting a brand new session...[/bold yellow]")
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

    console.print("[bold yellow]Describe your strategic dilemma, or type /history to load a past session:[/bold yellow]")
    console.print("[dim](Commands: /history, /new, /suspend, /help)[/dim]\n")

    initial_input = Prompt.ask("[bold green]Your Problem (or /history)[/bold green]").strip()
    if not initial_input:
        console.print("[red]No input provided. Exiting.[/red]")
        return

    if initial_input.lower() in ("/history", "history"):
        await handle_history_command(orchestrator)
        if not orchestrator.current_problem:
            initial_input = Prompt.ask("\n[bold green]Your Problem[/bold green]").strip()
            if not initial_input:
                return
            await run_problem_session(orchestrator, initial_input)
    elif initial_input.lower() in ("/help", "help"):
        show_help()
        initial_input = Prompt.ask("\n[bold green]Your Problem[/bold green]").strip()
        if not initial_input:
            return
        await run_problem_session(orchestrator, initial_input)
    else:
        await run_problem_session(orchestrator, initial_input)

    # Interactive Chat / Follow-up loop
    console.print("\n[bold cyan]💬 The board is now open for follow-up questions and discussion.[/bold cyan]")
    console.print("[dim]Commands: /suspend (pivot in same session), /new (fresh session), /history (load session), /help[/dim]\n")

    while True:
        try:
            user_input = Prompt.ask("[bold blue]You[/bold blue]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session terminated.[/dim]")
            break

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in ("/exit", "exit", "quit", ":q"):
            console.print("[bold green]Thank you for consulting your Board of Advisors. Good luck with your execution![/bold green]")
            break
        elif cmd in ("/help", "help"):
            show_help()
            continue
        elif cmd in ("/advisors", "advisors"):
            render_advisors_table(orchestrator.advisors)
            continue
        elif cmd in ("/plan", "plan"):
            if orchestrator.final_plan:
                render_plan(orchestrator.final_plan)
            else:
                console.print("[dim]No plan generated yet.[/dim]")
            continue
        elif cmd in ("/memory", "memory", "memories"):
            show_memories(orchestrator)
            continue
        elif cmd in ("/history", "history"):
            await handle_history_command(orchestrator)
            continue
        elif cmd in ("/suspend", "suspend"):
            await handle_suspend_command(orchestrator)
            continue
        elif cmd in ("/new", "new"):
            await handle_new_command(orchestrator)
            continue

        # Normal follow-up to the board
        with console.status("[bold cyan]Advisors are reviewing your follow-up...[/bold cyan]", spinner="dots"):
            await orchestrator.handle_user_followup(user_input)

if __name__ == "__main__":
    asyncio.run(main())
