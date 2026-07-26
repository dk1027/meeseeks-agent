"""Shared Rich console, theme, and banner for the meeseeks CLI."""

from __future__ import annotations

from rich.console import Console
from rich.text import Text
from rich.theme import Theme

THEME = Theme(
    {
        "brand": "bold #5EE6C4",
        "brand.dim": "#3A8F7C",
        "accent": "#7AA2F7",
        "muted": "dim white",
        "ok": "bold #5EE6C4",
        "warn": "bold #E0AF68",
        "error": "bold #F7768E",
        "path": "italic #7AA2F7",
        "cmd": "bold white",
    }
)

console = Console(theme=THEME, highlight=False)
error_console = Console(theme=THEME, stderr=True, highlight=False)

_WORDMARK = "m e e s e e k s"


def render_banner(version: str) -> Text:
    """Return the styled wordmark + tagline shown on bare invocation."""
    banner = Text()
    banner.append(" ᓚᘏᗢ  ", style="brand")
    banner.append(_WORDMARK, style="brand")
    banner.append(f"  v{version}\n", style="muted")
    banner.append("   don't tell me it is done — show me it is done", style="brand.dim italic")
    return banner


def not_implemented(command: str) -> None:
    """Standard message printed by command stubs during scaffolding."""
    console.print(f"[warn]○ not yet implemented:[/warn] [cmd]meeseeks {command}[/cmd]")
    console.print(f"[muted]this command is scaffolded but its behavior ships in a later change.[/muted]")
