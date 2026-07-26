"""Tests for the Textual plan-explorer shell (`meeseeks.plan_tui`).

Fixtures build `ExecutionPackage`/`Workstream`/`WorkPackage`/`TaskContract`
objects directly via their dataclass constructors rather than round-tripping
through TOML files or `load_execution_package`, so these tests stay
independent of any in-flight changes to the loader itself.

Uses Textual's built-in headless test harness (`App.run_test()` / `Pilot`),
which does not require an interactive terminal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from meeseeks.plan import ExecutionPackage, TaskContract, WorkPackage, Workstream
from meeseeks.plan_tui.app import PlanApp
from meeseeks.plan_tui.navigator import WBSTree
from meeseeks.plan_tui.screens import HelpScreen


def _task(package_id: str, title: str) -> TaskContract:
    return TaskContract(
        version=1,
        id=package_id,
        title=title,
        description=f"Description for {package_id}.",
        out_of_scope=(),
        acceptance_criteria=(),
        verification_commands=(),
        path=Path(f"tasks/{package_id}.toml"),
    )


def build_package() -> ExecutionPackage:
    """A small, deterministic two-workstream, three-package fixture."""
    foundation = Workstream(id="foundation", title="Foundation", ownership=("src/model/**",))
    tui = Workstream(id="tui", title="TUI", ownership=("src/plan_tui/**",))

    work_packages = (
        WorkPackage(
            id="WP-1.1.1",
            wbs="1.1.1",
            workstream_id="foundation",
            task_path=Path("tasks/01.toml"),
            task=_task("WP-1.1.1", "Architecture"),
        ),
        WorkPackage(
            id="WP-1.1.2",
            wbs="1.1.2",
            workstream_id="foundation",
            task_path=Path("tasks/02.toml"),
            task=_task("WP-1.1.2", "Models"),
        ),
        WorkPackage(
            id="WP-1.2.1",
            wbs="1.2.1",
            workstream_id="tui",
            task_path=Path("tasks/03.toml"),
            task=_task("WP-1.2.1", "TUI shell"),
        ),
    )

    return ExecutionPackage(
        version=1,
        title="Sample plan",
        path=Path("plan.toml"),
        workstreams=(foundation, tui),
        work_packages=work_packages,
        dependencies=(),
    )


def _labels(tree: WBSTree) -> list[str]:
    """Flatten every node's plain-text label, in tree order."""
    labels: list[str] = []

    def walk(node) -> None:
        labels.append(str(node.label))
        for child in node.children:
            walk(child)

    for child in tree.root.children:
        walk(child)
    return labels


@pytest.mark.asyncio
async def test_shell_startup_shows_title_and_all_workstreams_and_packages() -> None:
    package = build_package()
    app = PlanApp(package)
    async with app.run_test():
        assert app.sub_title == "Sample plan"

        tree = app.query_one(WBSTree)
        labels = _labels(tree)

        for workstream in package.workstreams:
            assert any(workstream.id in label and workstream.title in label for label in labels)
        for work_package in package.work_packages:
            assert any(
                work_package.id in label and work_package.task.title in label
                for label in labels
            )


@pytest.mark.asyncio
async def test_shell_startup_orders_packages_by_wbs_within_their_workstream() -> None:
    package = build_package()
    app = PlanApp(package)
    async with app.run_test():
        tree = app.query_one(WBSTree)
        foundation_node = tree.root.children[0]
        child_ids = [child.data.work_package.id for child in foundation_node.children]
        assert child_ids == ["WP-1.1.1", "WP-1.1.2"]


@pytest.mark.asyncio
async def test_navigation_down_arrow_moves_selection() -> None:
    package = build_package()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        start_line = tree.cursor_line
        await pilot.press("down")
        assert tree.cursor_line == start_line + 1


@pytest.mark.asyncio
async def test_navigation_j_and_k_move_selection_like_arrows() -> None:
    package = build_package()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        # Start from a known, non-boundary position.
        await pilot.press("down")
        start_line = tree.cursor_line
        await pilot.press("j")
        assert tree.cursor_line == start_line + 1
        await pilot.press("k")
        assert tree.cursor_line == start_line


@pytest.mark.asyncio
async def test_navigation_enter_inspects_a_work_package() -> None:
    package = build_package()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        # Move onto the first work package under "foundation" (index 1: the
        # workstream row is index 0).
        tree.cursor_line = 1
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        detail = app.query_one("#detail")
        assert "WP-1.1.1" in detail.text
        assert "Architecture" in detail.text


@pytest.mark.asyncio
async def test_navigation_enter_collapses_and_expands_a_workstream() -> None:
    package = build_package()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        workstream_node = tree.root.children[0]
        assert workstream_node.is_expanded

        tree.cursor_line = 0
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert not workstream_node.is_expanded

        await pilot.press("enter")
        await pilot.pause()
        assert workstream_node.is_expanded


@pytest.mark.asyncio
async def test_help_key_shows_contextual_help_and_can_be_dismissed() -> None:
    package = build_package()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, HelpScreen)


@pytest.mark.asyncio
async def test_quit_key_exits_cleanly() -> None:
    package = build_package()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()
        assert not app.is_running
