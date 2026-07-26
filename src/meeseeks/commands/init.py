"""`meeseeks init` — scaffold a .meeseeks directory in the current repository."""

from __future__ import annotations

import typer

from meeseeks.console import not_implemented


def init(
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite an existing [path].meeseeks[/path] directory.",
    ),
) -> None:
    """Create [path].meeseeks/config.toml[/path] and an example task in this repository."""
    not_implemented("init")
    raise typer.Exit(code=1)
