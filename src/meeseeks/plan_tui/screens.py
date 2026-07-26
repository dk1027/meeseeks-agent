"""Modal screens for the plan explorer shell."""

from __future__ import annotations

from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Static

HELP_TEXT = """\
[b]Keyboard help[/b]

  up / down, j / k    Move selection
  enter               Expand, collapse, or inspect
  ?                   Show this help
  q                   Quit
  escape               Close this help
"""


class HelpScreen(ModalScreen[None]):
    """Contextual help overlay listing the documented key bindings."""

    BINDINGS = [
        Binding("escape", "dismiss_help", "Close", show=False),
        Binding("q", "dismiss_help", "Close", show=False),
        Binding("question_mark", "dismiss_help", "Close", show=False),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > Container {
        width: auto;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    """

    def compose(self):
        with Container():
            yield Static(HELP_TEXT, id="help-text")

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
