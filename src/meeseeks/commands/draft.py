"""`meeseeks draft` — guided authoring of a task TOML file."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from meeseeks.console import not_implemented

DEFAULT_OUTPUT = Path(".meeseeks/task.toml")


def draft(
    output_path: Optional[Path] = typer.Argument(
        None,
        help=f"Where to write the task file. Defaults to [path]{DEFAULT_OUTPUT}[/path].",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite the output file if it already exists.",
    ),
) -> None:
    """Guide the user through title, acceptance criteria, and verification commands."""
    not_implemented("draft")
    raise typer.Exit(code=1)
