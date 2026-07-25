"""meeseeks: independent software change verification agent.

CLI entry point. Wires the init/draft/verify command shells together and
renders the banner shown on a bare invocation.
"""

from __future__ import annotations

import typer

from meeseeks import __version__
from meeseeks.commands.draft import draft
from meeseeks.commands.init import init
from meeseeks.commands.verify import verify
from meeseeks.console import console, render_banner

app = typer.Typer(
    name="meeseeks",
    help="Give it a task and acceptance criteria; it verifies your work with evidence.",
    rich_markup_mode="rich",
    no_args_is_help=False,
    add_completion=False,
)

app.command(name="init")(init)
app.command(name="draft")(draft)
app.command(name="verify")(verify)


def _version_callback(value: bool) -> None:
    if value:
        console.print(__version__)
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the meeseeks version and exit.",
    ),
) -> None:
    if ctx.invoked_subcommand is None:
        console.print(render_banner(__version__))
        console.print()
        console.print(ctx.get_help())


if __name__ == "__main__":
    app()
