"""`meeseeks verify` — adversarially verify a task against the repository."""

from __future__ import annotations

from pathlib import Path

import typer

from meeseeks.console import not_implemented


def verify(
    task_file: Path = typer.Argument(
        ...,
        help="Path to the task TOML file to verify.",
        exists=False,
    ),
) -> None:
    """Run verification commands, inspect the repository, and write a verdict report."""
    not_implemented("verify")
    raise typer.Exit(code=1)
