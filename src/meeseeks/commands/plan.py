"""`meeseeks plan` — launch the read-only WBS explorer for an execution package."""

from __future__ import annotations

from pathlib import Path

import typer

from meeseeks.console import error_console
from meeseeks.plan import PlanLoadError, load_execution_package
from meeseeks.plan_tui.app import PlanApp

DEFAULT_PLAN_PATH = Path(".meeseeks") / "plan.toml"


def _resolve_plan_path(plan_path: Path | None) -> Path:
    """Return the plan.toml to load, applying the discovery rule from AC-2.

    An explicit `plan_path` always takes precedence. Otherwise, look for the
    fixed `.meeseeks/plan.toml` location relative to the current working
    directory — no upward directory search, no multiple named plans (that's
    out of scope for this command).
    """
    if plan_path is not None:
        return plan_path

    if not DEFAULT_PLAN_PATH.exists():
        error_console.print(
            f"[error]✗ no plan found:[/error] [path]{DEFAULT_PLAN_PATH}[/path] "
            "does not exist in the current directory."
        )
        error_console.print(
            "[muted]pass a path explicitly, e.g. "
            "[cmd]meeseeks plan path/to/plan.toml[/cmd].[/muted]"
        )
        raise typer.Exit(code=1)

    return DEFAULT_PLAN_PATH


def plan(
    plan_path: Path | None = typer.Argument(
        None,
        help="Path to the execution package's plan.toml. "
        "Defaults to [path].meeseeks/plan.toml[/path] in the current directory.",
        exists=False,
    ),
) -> None:
    """Load an execution package and open it in the read-only WBS explorer."""
    resolved_path = _resolve_plan_path(plan_path)

    try:
        package = load_execution_package(resolved_path)
    except PlanLoadError as exc:
        error_console.print(f"[error]✗ could not load plan:[/error] {exc}")
        raise typer.Exit(code=1) from exc

    try:
        PlanApp(package).run()
    except Exception as exc:  # noqa: BLE001 - convert a TUI crash into a clean exit
        error_console.print(f"[error]✗ meeseeks plan crashed:[/error] {exc}")
        raise typer.Exit(code=1) from exc
