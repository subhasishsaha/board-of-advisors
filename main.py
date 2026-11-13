import asyncio
import sys
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt

from board.config import DEFAULT_MODEL, DEFAULT_EFFORT
from board.cli_ui import (
    console,
    render_banner,
    render_advisors_table,
    render_message,
    render_plan,
)
from board.orchestrator import BoardOrchestrator, BoardMessage

def show_help():
    console.print("""
[bold cyan]Available Commands:[/bold cyan]
  [yellow]/new[/yellow]       - Convene a new bespoke board for a new dilemma
  [yellow]/advisors[/yellow]  - Show active board members and their tags
  [yellow]/plan[/yellow]      - Review the consolidated Plan of Action
  [yellow]/memory[/yellow]    - View what advisors have stored in persistent memory
  [yellow]/help[/yellow]      - Show this help message
  [yellow]/exit[/yellow]      - Exit the session
""", style="white")

def show_memories(orchestrator: BoardOrchestrator):
    console.print("\n[bold cyan]🧠 Persistent Advisor Memories:[/bold cyan]")
    for adv in orchestrator.advisors:
        mem_text = adv.memory.format_memory_for_prompt()
        console.print(f"\n[bold {adv.color}]{adv.avatar} {adv.name} ({adv.tag}) Memory:[/bold {adv.color}]")
        console.print(mem_text, style="dim")
    console.print()

async def run_problem_session(orchestrator: BoardOrchestrator, problem: str):
    """Dynamically assemble board and run deliberation for a given problem."""
    # 1. Dynamic Advisor Generation
    with console.status("[bold cyan]🔍 Analyzing decision problem and assembling bespoke Board of Advisors...[/bold cyan]", spinner="dots"):
        advisors = await orchestrator.build_dynamic_advisors(problem)

    console.print(f"\n[bold green]🏛️ Successfully assembled a bespoke board of {len(advisors)} advisors tailored to your problem:[/bold green]\n")
    render_advisors_table(advisors)

    # 2. Multi-Stage Deliberation (at most 3 rounds)
    with console.status("[bold cyan]🏛️ The Board of Advisors is convening and deliberating (max 3 rounds)...[/bold cyan]", spinner="dots"):
        plan = await orchestrator.run_deliberation(problem=problem)

    console.print("\n[bold green]✅ Deliberation concluded and Action Plan synthesized![/bold green]\n")
    render_plan(plan)

async def main():
    render_banner()
    console.print(f"[dim]Backend: agy CLI detached mode  |  Model: {DEFAULT_MODEL}  |  Effort: {DEFAULT_EFFORT}[/dim]\n")

    # Initialize the orchestrator with real-time UI callback
    orchestrator = None

    def on_message(msg: BoardMessage):
        if orchestrator:
            render_message(msg, orchestrator.advisors_by_tag)

    try:
        orchestrator = BoardOrchestrator(on_message_callback=on_message)
    except Exception as e:
        console.print(f"[bold red]Initialization Error:[/bold red] {e}")
        sys.exit(1)

    console.print("[bold yellow]Describe your strategic dilemma, business challenge, or decision below:[/bold yellow]")
    console.print("[dim](The orchestrator will dynamically assemble a tailored board of at most 10 specialist advisors to deliberate.)[/dim]\n")

    initial_problem = Prompt.ask("[bold green]Your Problem[/bold green]").strip()
    if not initial_problem:
        console.print("[red]No problem provided. Exiting.[/red]")
        return

    await run_problem_session(orchestrator, initial_problem)

    # Interactive Chat / Follow-up loop
    console.print("\n[bold cyan]💬 The board is now open for follow-up questions and discussion.[/bold cyan]")
    console.print("[dim]You can ask follow-ups or tag specific members (e.g. '@Advisor what if revenues drop?'). Type /help for options.[/dim]\n")

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
        elif cmd in ("/new", "new"):
            new_problem = Prompt.ask("\n[bold yellow]Enter new problem for the board[/bold yellow]").strip()
            if new_problem:
                await run_problem_session(orchestrator, new_problem)
            continue

        # Normal follow-up to the board
        with console.status("[bold cyan]Advisors are reviewing your follow-up...[/bold cyan]", spinner="dots"):
            await orchestrator.handle_user_followup(user_input)

if __name__ == "__main__":
    asyncio.run(main())
