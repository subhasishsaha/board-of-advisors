import sys
from typing import Callable, List, Optional
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

SLASH_COMMANDS = [
    ("/new", "Start a fresh session with bespoke advisors"),
    ("/history", "Browse saved sessions to load or delete ('d #')"),
    ("/delete", "Delete a saved session by index or ID"),
    ("/cls", "Clear current session slate without starting a new session"),
    ("/set-max-agents", "Set max dynamic advisors for this thread (default: 10)"),
    ("/set-round-tables", "Set deliberation rounds for this thread (default: 3)"),
    ("/advisors", "Show active board members and their tags"),
    ("/plan", "Review the consolidated Plan of Action"),
    ("/memory", "View persistent advisor memories"),
    ("/help", "Show full command help & guidelines"),
    ("/exit", "Exit the council session"),
]

COMPLETION_STYLE = Style.from_dict({
    # Floating autocomplete dropdown styling
    "completion-menu": "bg:#21252b #abb2bf",
    "completion-menu.completion": "bg:#21252b #abb2bf",
    "completion-menu.completion.current": "bg:#3e4451 #61afef bold",
    "completion-menu.meta.completion": "bg:#21252b #5c6370",
    "completion-menu.meta.completion.current": "bg:#3e4451 #98c379 italic",
    "scrollbar.background": "bg:#21252b",
    "scrollbar.button": "bg:#4b5263",
})

class BoardSlashCompleter(Completer):
    """
    Live autocomplete dropdown triggered as soon as the user types '/' (or '@' for advisors),
    matching the interactive experience of Claude Code and Google Antigravity.
    Prevents slash command chaining by suppressing completions once a command is typed.
    """

    def __init__(self, get_advisors_fn: Optional[Callable[[], List]] = None):
        self.get_advisors_fn = get_advisors_fn

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # 1. Slash commands autocomplete
        if text.startswith("/"):
            # Suppress slash completions if a space is typed (prevents chaining)
            if " " in text:
                return

            word = text.lower()
            for cmd, desc in SLASH_COMMANDS:
                if cmd.lower().startswith(word):
                    yield Completion(
                        text=cmd,
                        start_position=-len(text),
                        display=cmd,
                        display_meta=desc,
                    )
            return

        # 2. @Advisor tagging autocomplete during deliberation
        if self.get_advisors_fn:
            words = text.split()
            current_word = words[-1] if words and not text.endswith(" ") else (text if not text.endswith(" ") else "")
            if current_word.startswith("@"):
                advisors = self.get_advisors_fn() or []
                prefix = current_word.lower()
                for adv in advisors:
                    adv_tag = getattr(adv, "tag", "")
                    adv_name = getattr(adv, "name", "")
                    adv_avatar = getattr(adv, "avatar", "👤")
                    adv_role = getattr(adv, "role", "Advisor")
                    if adv_tag and adv_tag.lower().startswith(prefix):
                        yield Completion(
                            text=adv_tag,
                            start_position=-len(current_word),
                            display=f"{adv_avatar} {adv_tag}",
                            display_meta=f"{adv_name} ({adv_role[:28]})",
                        )


def get_interactive_prompt_session(get_advisors_fn: Optional[Callable[[], List]] = None) -> Optional[PromptSession]:
    """
    Returns an interactive PromptSession with live dropdown completion if running
    in an interactive TTY, or None in non-interactive / piped environments.
    """
    try:
        if sys.stdin.isatty():
            completer = BoardSlashCompleter(get_advisors_fn=get_advisors_fn)
            return PromptSession(
                completer=completer,
                complete_while_typing=True,
                style=COMPLETION_STYLE,
                history=InMemoryHistory(),
            )
    except Exception:
        pass
    return None
