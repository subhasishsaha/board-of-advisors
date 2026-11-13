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
        panel = Panel(
            highlight_tags(msg.content),
            title="👤 You (User)",
            title_align="left",
            border_style="blue",
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
