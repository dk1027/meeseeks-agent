"""Scaffold-level tests: the CLI is wired up correctly.

These do not test command behavior — init/draft/verify are stubs until
implemented in later changes. They only confirm the app assembles, the
commands are registered, and each stub reports "not implemented" rather
than silently succeeding or crashing.
"""

from typer.testing import CliRunner

from meeseeks.cli import app

runner = CliRunner()


def test_bare_invocation_shows_banner_and_help():
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "meeseeks" in result.output
    assert "init" in result.output
    assert "draft" in result.output
    assert "verify" in result.output


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip()


def test_commands_are_registered_and_show_help():
    for command in ("init", "draft", "verify"):
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0, result.output


def test_init_stub_reports_not_implemented():
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 1
    assert "not yet implemented" in result.output


def test_draft_stub_reports_not_implemented():
    result = runner.invoke(app, ["draft"])
    assert result.exit_code == 1
    assert "not yet implemented" in result.output


def test_verify_stub_requires_task_file():
    result = runner.invoke(app, ["verify"])
    assert result.exit_code != 0


def test_verify_stub_reports_not_implemented():
    result = runner.invoke(app, ["verify", "some-task.toml"])
    assert result.exit_code == 1
    assert "not yet implemented" in result.output
