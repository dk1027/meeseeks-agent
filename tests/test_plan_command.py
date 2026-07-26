"""Tests for `meeseeks plan`: discovery, validation, and TUI launch wiring.

Success-path tests stub `PlanApp.run` so the suite never tries to take over
a real terminal; they assert instead that the loader was called with the
right path and that `PlanApp` was constructed from the resulting package.
Failure-path tests let the real `load_execution_package` validation run and
assert on exit code and rendered output.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from meeseeks.cli import app
from meeseeks.commands import plan as plan_command
from meeseeks.plan import ExecutionPackage

runner = CliRunner()

FIXTURES = Path(__file__).parent / "fixtures" / "plans"


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
