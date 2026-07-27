"""Tests for `meeseeks plan`: discovery, validation, and TUI launch wiring.

Success-path tests stub `PlanApp.run` so the suite never tries to take over
a real terminal; they assert instead that the loader was called with the
right path and that `PlanApp` was constructed from the resulting package.
Failure-path tests let the real `load_execution_package` validation run and
assert on exit code and rendered output.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest
from textual.widgets import OptionList
from typer.testing import CliRunner

from meeseeks.cli import app
from meeseeks.commands import plan as plan_command
from meeseeks.plan import ExecutionPackage
from meeseeks.plan_tui.app import PlanApp
from meeseeks.plan_tui.navigator import WBSTree
from meeseeks.plan_tui.screens import DependencyScreen, HelpScreen

runner = CliRunner()

FIXTURES = Path(__file__).parent / "fixtures" / "plans"
REPRESENTATIVE_PLAN = FIXTURES / "representative" / "plan.toml"


@pytest.fixture
def stub_plan_app(monkeypatch):
    """Replace `PlanApp` with a stub that records its package and never runs a TUI."""

    calls: list[ExecutionPackage] = []

    class _StubPlanApp:
        def __init__(self, package: ExecutionPackage) -> None:
            calls.append(package)

        def run(self) -> None:
            return None

    monkeypatch.setattr(plan_command, "PlanApp", _StubPlanApp)
    return calls


def test_plan_with_explicit_path_loads_and_launches(stub_plan_app):
    result = runner.invoke(app, ["plan", str(FIXTURES / "valid" / "plan.toml")])

    assert result.exit_code == 0, result.output
    assert len(stub_plan_app) == 1
    assert stub_plan_app[0].title == "Fixture plan"


def test_plan_without_path_discovers_dot_meeseeks_plan(stub_plan_app, monkeypatch):
    monkeypatch.chdir(FIXTURES / "discovery")

    result = runner.invoke(app, ["plan"])

    assert result.exit_code == 0, result.output
    assert len(stub_plan_app) == 1
    assert stub_plan_app[0].title == "Discovery fixture plan"


def test_plan_without_path_and_no_discoverable_plan_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["plan"])

    assert result.exit_code == 1
    assert ".meeseeks/plan.toml" in result.output


def test_plan_missing_file_fails_before_tui(tmp_path):
    missing = tmp_path / "does-not-exist" / "plan.toml"

    result = runner.invoke(app, ["plan", str(missing)])

    assert result.exit_code == 1
    assert "file not found" in result.output


def test_plan_malformed_plan_fails_before_tui():
    result = runner.invoke(
        app, ["plan", str(FIXTURES / "invalid_malformed" / "plan.toml")]
    )

    assert result.exit_code == 1
    assert "missing required field" in result.output


def test_plan_missing_referenced_task_fails_before_tui():
    result = runner.invoke(
        app, ["plan", str(FIXTURES / "invalid_missing_task" / "plan.toml")]
    )

    assert result.exit_code == 1
    assert "file not found" in result.output


def test_plan_explicit_path_takes_precedence_over_discovery(stub_plan_app, monkeypatch):
    monkeypatch.chdir(FIXTURES / "discovery")

    result = runner.invoke(app, ["plan", str(FIXTURES / "valid" / "plan.toml")])

    assert result.exit_code == 0, result.output
    assert stub_plan_app[0].title == "Fixture plan"


def test_plan_mismatched_task_id_fails_before_tui():
    result = runner.invoke(
        app, ["plan", str(FIXTURES / "invalid_mismatched_task_id" / "plan.toml")]
    )

    assert result.exit_code == 1
    assert "does not match" in result.output


def test_plan_unknown_dependency_endpoint_fails_before_tui():
    result = runner.invoke(
        app, ["plan", str(FIXTURES / "invalid_unknown_dependency_endpoint" / "plan.toml")]
    )

    assert result.exit_code == 1
    assert "unknown successor work package" in result.output


def test_plan_dependency_cycle_fails_before_tui():
    result = runner.invoke(app, ["plan", str(FIXTURES / "invalid_cycle" / "plan.toml")])

    assert result.exit_code == 1
    output = " ".join(result.output.split())
    assert "dependency cycle detected" in output


def _hash_tree(root: Path) -> dict[str, str]:
    """Hash every file under `root`, keyed by its path relative to `root`."""
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_plan_end_to_end_interaction_through_public_command_is_read_only(monkeypatch):
    """AC-2/AC-3: drive the real public `meeseeks plan` command end to end.

    `_resolve_plan_path` and `load_execution_package` run for real against
    the representative fixture, and a real `PlanApp` is constructed from the
    resulting package. Only `PlanApp.run` is replaced, so that instead of
    taking over a real terminal it drives a scripted Textual `Pilot` session
    at 80x24 through the same instance the CLI already built. The script
    exercises WBS navigation (arrows and vim keys), full task-contract
    detail for the integration work package, dependency traversal with a
    jump to a neighbor, contextual help, and a clean quit. Every fixture
    file is hashed before and after to prove none of it was modified.
    """
    fixture_root = FIXTURES / "representative"
    before = _hash_tree(fixture_root)

    captured: dict[str, object] = {}

    async def _script(plan_app: PlanApp, pilot) -> None:
        tree = plan_app.query_one(WBSTree)

        # WBS navigation: down/j moves forward, k moves back, through the
        # real navigator built by the real CLI pipeline.
        start_line = tree.cursor_line
        await pilot.press("down")
        await pilot.pause()
        captured["down_delta"] = tree.cursor_line - start_line
        await pilot.press("j")
        await pilot.pause()
        captured["j_delta"] = tree.cursor_line - start_line
        await pilot.press("k")
        await pilot.pause()
        captured["k_delta"] = tree.cursor_line - start_line

        # Inspect the integration work package's full task-contract detail.
        tree.cursor_line = 8  # WP-1.3.1, the integration join.
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        captured["detail_text"] = plan_app.query_one("#detail").text

        # Dependency traversal: open dependencies, then jump to a prerequisite.
        await pilot.press("d")
        await pilot.pause()
        screen = plan_app.screen
        captured["dependency_screen_is_open"] = isinstance(screen, DependencyScreen)
        options = screen.query_one("#dep-options", OptionList)
        captured["dependency_options_text"] = " ".join(
            str(option.prompt) for option in options.options
        )
        option_id = next(
            option_id
            for option_id, neighbor_id in screen._targets.items()
            if neighbor_id == "WP-1.1.2"
        )
        options.highlighted = options.get_option_index(option_id)
        options.action_select()
        await pilot.pause()
        captured["dependency_jump_header_text"] = screen.query_one("#dep-header").text

        await pilot.press("escape")
        await pilot.pause()
        captured["screen_after_dependency_close_is_dependency_screen"] = isinstance(
            plan_app.screen, DependencyScreen
        )
        captured["detail_after_dependency_close"] = plan_app.query_one("#detail").text

        # Help.
        await pilot.press("question_mark")
        await pilot.pause()
        captured["help_screen_is_open"] = isinstance(plan_app.screen, HelpScreen)
        await pilot.press("escape")
        await pilot.pause()

        # Exit.
        await pilot.press("q")
        await pilot.pause()
        captured["is_running_after_quit"] = plan_app.is_running

    async def _run(self: PlanApp) -> None:
        async with self.run_test(size=(80, 24)) as pilot:
            await _script(self, pilot)

    def _stub_run(self: PlanApp) -> None:
        asyncio.run(_run(self))

    monkeypatch.setattr(PlanApp, "run", _stub_run)

    result = runner.invoke(app, ["plan", str(REPRESENTATIVE_PLAN)])

    assert result.exit_code == 0, result.output

    assert captured["down_delta"] == 1
    assert captured["j_delta"] == 2
    assert captured["k_delta"] == 1  # back down to one step from start

    detail_text = captured["detail_text"]
    assert "WP-1.3.1" in detail_text
    assert "Integrated plan command" in detail_text
    assert "Rolling back a partially integrated feature" in detail_text
    assert "AC-1" in detail_text
    assert "AC-2" in detail_text
    assert "AC-3" in detail_text
    assert "uv run pytest tests/test_plan_command.py" in detail_text
    assert "uv run ruff check src/meeseeks/commands/plan.py" in detail_text

    assert captured["dependency_screen_is_open"] is True
    dependency_text = captured["dependency_options_text"]
    assert "WP-1.1.2" in dependency_text
    assert "WP-1.2.2" in dependency_text
    assert "integration" in dependency_text

    jump_header = captured["dependency_jump_header_text"]
    assert "WP-1.1.2" in jump_header
    assert "Loader and graph validation" in jump_header

    assert captured["screen_after_dependency_close_is_dependency_screen"] is False
    assert "WP-1.1.2" in captured["detail_after_dependency_close"]

    assert captured["help_screen_is_open"] is True
    assert captured["is_running_after_quit"] is False

    after = _hash_tree(fixture_root)
    assert after == before
