import re
from typing import Optional
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from board.orchestrator import BoardMessage

console = Console()

def render_banner() -> None:
    """Render the welcome banner for Board of Advisors."""
    banner_text = Text()
    banner_text.append("🏛️  EXECUTIVE BOARD OF ADVISORS\n", style="bold white")
    banner_text.append("Autonomous Multi-Agent Decision Council  •  Powered by Gemini 3.8 Flash (agy detached)", style="dim cyan")
    
    panel = Panel(
        banner_text,
        border_style="bright_blue",
        box=box.DOUBLE,
        padding=(1, 2),
    )
    console.print(panel)

def render_advisors_table(advisors: list) -> None:
    """Render table of active board members."""
    table = Table(
        title="🏛️ Active Board of Advisors",
        box=box.ROUNDED,
        header_style="bold cyan",
        title_style="bold white",
    )
    table.add_column("Tag", style="bold yellow", width=12)
    table.add_column("Advisor", style="bold white", width=20)
    table.add_column("Role", style="green", width=36)
    table.add_column("Expertise / Angle", style="dim", width=45)

    for adv in advisors:
        beliefs = getattr(adv, "core_beliefs", None) or (adv.memory.core_beliefs if hasattr(adv, "memory") else [])
        summary = beliefs[0] if beliefs else (adv.bio[:45] if hasattr(adv, "bio") else "")
        table.add_row(
            f"{adv.avatar} {adv.tag}",
            adv.name,
            adv.role,
            summary,
        )

    console.print(table)
    console.print()

def render_sessions_history_table(sessions: list) -> None:
    """Render table of previous deliberation sessions with load/delete action guidance."""
    table = Table(
        title="📜 Previous Deliberation Sessions",
        caption="[dim]Options: Enter [bold cyan]#[/bold cyan] to load session  •  [bold red]d #[/bold red] (e.g. 'd 2') to delete  •  [bold yellow]Enter[/bold yellow] to cancel[/dim]",
        caption_justify="center",
        box=box.ROUNDED,
        header_style="bold cyan",
        title_style="bold white",
    )
    table.add_column("#", style="bold yellow", width=4, justify="center")
    table.add_column("Session Date/ID", style="bold white", width=18)
    table.add_column("Problem Snippet", style="cyan", width=44)
    table.add_column("Advisors", style="dim", width=28)
    table.add_column("Turns", style="green", width=6, justify="center")
    table.add_column("Plan", style="magenta", width=6, justify="center")

    for idx, s in enumerate(sessions, 1):
        ts = s.get("timestamp", "")
        date_str = ts.split("T")[0] + " " + ts.split("T")[1][:5] if "T" in ts else s.get("session_id", "")
        prob = s.get("problem", "")
        prob_snippet = (prob[:41] + "...") if len(prob) > 44 else prob
        advs = ", ".join(s.get("advisors", []))
        if len(advs) > 28:
            advs = advs[:25] + "..."
        has_plan = "✅" if s.get("has_plan") else "❌"

        table.add_row(
            str(idx),
            date_str,
            prob_snippet,
            advs,
            str(s.get("message_count", 0)),
            has_plan,
        )

    console.print(table)
    console.print()

def render_slash_menu(has_board: bool = False, has_plan: bool = False) -> None:
    """Render an interactive options menu showing all available slash commands."""
    table = Table(
        title="🧭 Available Slash Commands",
        box=box.ROUNDED,
        header_style="bold cyan",
        title_style="bold white",
        caption="[dim]Tip: Enter command (e.g. [bold yellow]/history[/bold yellow]) or option number [bold yellow][1-11][/bold yellow]  •  Chaining is blocked[/dim]",
        caption_justify="center",
    )
    table.add_column("#", style="bold yellow", width=4, justify="center")
    table.add_column("Command", style="bold cyan", width=22)
    table.add_column("Description", style="white", width=44)
    table.add_column("Context Status", style="dim", width=18, justify="center")

    status_board = "[green]Active[/green]" if has_board else "[dim]No board yet[/dim]"
    status_plan = "[green]Ready[/green]" if has_plan else "[dim]Not generated[/dim]"

    commands_data = [
        ("1", "/new [problem]", "Start a fresh session with bespoke advisors", "[cyan]Available[/cyan]"),
        ("2", "/history", "Browse saved sessions to load or delete ('d #')", "[cyan]Available[/cyan]"),
        ("3", "/delete <#>", "Delete a saved session by index or ID", "[cyan]Available[/cyan]"),
        ("4", "/cls", "Clear current session slate without starting new session", "[cyan]Available[/cyan]"),
        ("5", "/advisors", "Show active board members and their tags", status_board),
        ("6", "/plan", "Review the consolidated Plan of Action", status_plan),
        ("7", "/memory", "View persistent advisor memories", status_board),
        ("8", "/help", "Show full command help & guidelines", "[cyan]Available[/cyan]"),
        ("9", "/set-max-agents <#>", "Set max dynamic advisors for this thread", "[cyan]Thread config[/cyan]"),
        ("10", "/set-round-tables <#>", "Set deliberation rounds for this thread", "[cyan]Thread config[/cyan]"),
        ("11", "/exit", "Exit the council session", "[dim]Quit[/dim]"),
    ]

    for num, cmd_name, desc, status in commands_data:
        table.add_row(num, cmd_name, desc, status)

    console.print(table)
    console.print()

def highlight_tags(text: str) -> Text:
    """Highlight @Advisor tags in message body."""
    rich_text = Text()
    pattern = re.compile(r"(@\w+)")
    parts = pattern.split(text)

    for part in parts:
        if part.startswith("@"):
            rich_text.append(part, style="bold bright_yellow underline")
        else:
            rich_text.append(part)
    return rich_text

def render_message(msg: BoardMessage, advisor_map: dict) -> None:
    """Render an individual advisor message with rich panel styling."""
    if msg.sender == "USER":
        title = "👤 You (User)"
        if "user_input" in msg.stage or "clarification" in msg.stage:
            title = "👤 You (User)  [In-Deliberation Input / Clarification]"
        panel = Panel(
            highlight_tags(msg.content),
            title=title,
            title_align="left",
            border_style="bright_blue",
            box=box.ROUNDED,
            padding=(0, 1),
        )
        console.print(panel)
        return

    if msg.sender == "CHAIR / SYNTHESIS":
        md = Markdown(msg.content)
        panel = Panel(
            md,
            title="📋 CONSOLIDATED PLAN OF ACTION",
            title_align="center",
            border_style="bright_green",
            box=box.DOUBLE,
            padding=(1, 2),
        )
        console.print(panel)
        return

    # Advisor message
    adv = advisor_map.get(msg.tag.lower())
    avatar = adv.avatar if adv else "👤"
    color = adv.color if adv else "cyan"
    role = adv.role if adv else "Advisor"

    stage_badge = ""
    if "opening" in msg.stage or msg.stage == "initial_assessment":
        stage_badge = "[Round 1 - Opening Assessment]"
    elif "final" in msg.stage:
        stage_badge = "[Round 3 - Final Deliberation & Verdict]"
    elif "round_2" in msg.stage or "debate" in msg.stage:
        stage_badge = "[Round 2 - Cross-Examination]"
    elif msg.stage == "followup_response":
        stage_badge = "[Follow-up Response]"

    title = f"{avatar} {msg.sender} ({msg.tag})  •  {role}  {stage_badge}"
    body = highlight_tags(msg.content)

    panel = Panel(
        body,
        title=title,
        title_align="left",
        border_style=color,
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print(panel)

def render_plan(plan_text: str) -> None:
    """Render markdown action plan."""
    md = Markdown(plan_text)
    panel = Panel(
        md,
        title="🎯 ACTION PLAN SUMMARY",
        title_align="center",
        border_style="bright_magenta",
        box=box.DOUBLE,
        padding=(1, 2),
    )
    console.print(panel)
