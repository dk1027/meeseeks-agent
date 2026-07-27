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
from textual.widgets import OptionList

from meeseeks.plan import (
    AcceptanceCriterion,
    Dependency,
    DependencyEdge,
    ExecutionPackage,
    TaskContract,
    WorkPackage,
    Workstream,
    WorkstreamEdge,
)
from meeseeks.plan_tui.app import PlanApp
from meeseeks.plan_tui.navigator import WBSTree
from meeseeks.plan_tui.screens import DependencyScreen, HelpScreen


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


def _task_with_contract_fields(
    package_id: str,
    title: str,
    *,
    description: str = "",
    out_of_scope: tuple[str, ...] = (),
    acceptance_criteria: tuple[AcceptanceCriterion, ...] = (),
    verification_commands: tuple[str, ...] = (),
) -> TaskContract:
    return TaskContract(
        version=1,
        id=package_id,
        title=title,
        description=description or f"Description for {package_id}.",
        out_of_scope=out_of_scope,
        acceptance_criteria=acceptance_criteria,
        verification_commands=verification_commands,
        path=Path(f"tasks/{package_id}.toml"),
    )


def build_package_with_relationships() -> ExecutionPackage:
    """Two workstreams with a cross-workstream dependency, so rollups and
    per-package prerequisite/dependent edges are populated directly (bypassing
    `load_execution_package`, per this file's fixture convention).
    """
    foundation = Workstream(
        id="foundation",
        title="Foundation",
        ownership=("src/model/**", "src/loader/**"),
        outgoing=(
            WorkstreamEdge(
                workstream_id="tui",
                type="hard",
                reason="TUI renders the loader's normalized model.",
            ),
        ),
    )
    tui = Workstream(
        id="tui",
        title="TUI",
        ownership=("src/plan_tui/**",),
        incoming=(
            WorkstreamEdge(
                workstream_id="foundation",
                type="hard",
                reason="TUI renders the loader's normalized model.",
            ),
        ),
    )

    upstream = WorkPackage(
        id="WP-1.1.1",
        wbs="1.1.1",
        workstream_id="foundation",
        task_path=Path("tasks/01.toml"),
        task=_task_with_contract_fields(
            "WP-1.1.1",
            "Architecture",
            description="Builds the normalized model.",
            out_of_scope=("Editing task contracts",),
            acceptance_criteria=(
                AcceptanceCriterion(id="AC-1", description="Loads a valid plan."),
            ),
            verification_commands=("uv run pytest tests/test_plan.py",),
        ),
        dependents=(
            DependencyEdge(
                package_id="WP-1.2.2",
                type="hard",
                reason="Detail pane renders the loader's model.",
            ),
        ),
    )
    downstream = WorkPackage(
        id="WP-1.2.2",
        wbs="1.2.2",
        workstream_id="tui",
        task_path=Path("tasks/04.toml"),
        task=_task_with_contract_fields(
            "WP-1.2.2",
            "Item details",
            description="Populates the detail pane.",
        ),
        prerequisites=(
            DependencyEdge(
                package_id="WP-1.1.1",
                type="hard",
                reason="Detail pane renders the loader's model.",
            ),
        ),
    )

    return ExecutionPackage(
        version=1,
        title="Relationships plan",
        path=Path("plan.toml"),
        workstreams=(foundation, tui),
        work_packages=(upstream, downstream),
        dependencies=(
            Dependency(
                predecessor="WP-1.1.1",
                successor="WP-1.2.2",
                type="hard",
                reason="Detail pane renders the loader's model.",
            ),
        ),
    )


def build_package_with_long_content() -> ExecutionPackage:
    """A single package whose description and acceptance criteria are long
    enough to require scrolling in the detail pane.
    """
    long_description = "\n".join(
        f"Paragraph {i}: this line has some bracket-y content like [not markup]."
        for i in range(60)
    )
    criteria = tuple(
        AcceptanceCriterion(id=f"AC-{i}", description=f"Criterion number {i} must hold.")
        for i in range(40)
    )
    workstream = Workstream(id="tui", title="TUI", ownership=("src/plan_tui/**",))
    work_package = WorkPackage(
        id="WP-1.2.2",
        wbs="1.2.2",
        workstream_id="tui",
        task_path=Path("tasks/04.toml"),
        task=_task_with_contract_fields(
            "WP-1.2.2",
            "Item details",
            description=long_description,
            acceptance_criteria=criteria,
        ),
    )
    return ExecutionPackage(
        version=1,
        title="Long content plan",
        path=Path("plan.toml"),
        workstreams=(workstream,),
        work_packages=(work_package,),
        dependencies=(),
    )


@pytest.mark.asyncio
async def test_details_workstream_selection_shows_all_fields_and_rollups() -> None:
    package = build_package_with_relationships()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        tree.cursor_line = 0
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        detail = app.query_one("#detail")
        text = detail.text

        assert "foundation" in text
        assert "Foundation" in text
        assert "src/model/**" in text
        assert "src/loader/**" in text
        assert "WP-1.1.1" in text
        assert "Architecture" in text
        assert "tui" in text
        assert "hard" in text
        assert "TUI renders the loader's normalized model." in text


@pytest.mark.asyncio
async def test_details_work_package_selection_shows_full_contract_and_graph_context() -> None:
    package = build_package_with_relationships()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        # Index 2 is the second work package (downstream, WP-1.2.2) under "tui":
        # 0=foundation, 1=WP-1.1.1, 2=tui, 3=WP-1.2.2.
        tree.cursor_line = 3
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        detail = app.query_one("#detail")
        text = detail.text

        assert "WP-1.2.2" in text
        assert "1.2.2" in text
        assert "tui" in text
        assert "tasks/04.toml" in text
        assert "Item details" in text
        assert "Populates the detail pane." in text
        assert "WP-1.1.1" in text
        assert "Detail pane renders the loader's model." in text


@pytest.mark.asyncio
async def test_details_work_package_shows_every_documented_task_contract_field() -> None:
    package = build_package_with_relationships()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        tree.cursor_line = 1  # WP-1.1.1, under "foundation".
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        detail = app.query_one("#detail")
        text = detail.text

        assert "Builds the normalized model." in text
        assert "Editing task contracts" in text
        assert "AC-1" in text
        assert "Loads a valid plan." in text
        assert "uv run pytest tests/test_plan.py" in text


@pytest.mark.asyncio
async def test_details_long_description_and_criteria_are_not_truncated() -> None:
    package = build_package_with_long_content()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        tree.cursor_line = 1  # The lone work package, under "tui".
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        detail = app.query_one("#detail")
        text = detail.text

        # Every paragraph and every acceptance criterion survives, including
        # bracket-y content that would otherwise be mistaken for markup.
        assert "Paragraph 0:" in text
        assert "Paragraph 59:" in text
        assert "[not markup]" in text
        assert "AC-0" in text
        assert "AC-39" in text
        assert "Criterion number 39 must hold." in text


@pytest.mark.asyncio
async def test_details_selecting_new_item_refreshes_pane_without_losing_navigator_focus() -> (
    None
):
    package = build_package_with_relationships()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        tree.cursor_line = 1
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        detail = app.query_one("#detail")
        assert "WP-1.1.1" in detail.text

        assert app.focused is tree

        tree.cursor_line = 3
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert "WP-1.2.2" in detail.text
        assert "Item details" in detail.text
        assert "Architecture" not in detail.text
        assert app.focused is tree


@pytest.mark.asyncio
async def test_dependency_key_opens_dependency_screen_for_cursor_selection() -> None:
    package = build_package_with_relationships()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        tree.cursor_line = 1  # WP-1.1.1, under "foundation".
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()

        assert isinstance(app.screen, DependencyScreen)


@pytest.mark.asyncio
async def test_dependency_screen_lists_workstream_incoming_and_outgoing_edges() -> None:
    """AC-1: every incoming/outgoing edge for a workstream, with endpoint,
    type, and full reason."""
    package = build_package_with_relationships()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        tree.cursor_line = 0  # "foundation" workstream.
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DependencyScreen)
        options = screen.query_one("#dep-options", OptionList)
        rendered = " ".join(str(option.prompt) for option in options.options)

        assert "tui" in rendered
        assert "hard" in rendered
        assert "TUI renders the loader's normalized model." in rendered


@pytest.mark.asyncio
async def test_dependency_screen_lists_work_package_prerequisites_and_dependents() -> None:
    """AC-1: every prerequisite/dependent edge for a work package, with
    endpoint, type, and full reason."""
    package = build_package_with_relationships()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        tree.cursor_line = 3  # WP-1.2.2, under "tui".
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DependencyScreen)
        options = screen.query_one("#dep-options", OptionList)
        rendered = " ".join(str(option.prompt) for option in options.options)

        assert "WP-1.1.1" in rendered
        assert "hard" in rendered
        assert "Detail pane renders the loader's model." in rendered


@pytest.mark.asyncio
async def test_dependency_screen_jump_navigates_to_neighbor_and_inspects_it() -> None:
    """AC-2: selecting a dependency edge jumps to that neighbor and shows
    its own details/edges."""
    package = build_package_with_relationships()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        tree.cursor_line = 3  # WP-1.2.2, under "tui".
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DependencyScreen)
        options = screen.query_one("#dep-options", OptionList)

        option_id = next(
            option_id
            for option_id, neighbor_id in screen._targets.items()
            if neighbor_id == "WP-1.1.1"
        )
        options.highlighted = options.get_option_index(option_id)
        options.action_select()
        await pilot.pause()

        header = screen.query_one("#dep-header")
        assert "WP-1.1.1" in header.text
        assert "Architecture" in header.text

        # WP-1.1.1's own dependents (WP-1.2.2) are now shown too.
        rendered = " ".join(str(option.prompt) for option in options.options)
        assert "WP-1.2.2" in rendered


@pytest.mark.asyncio
async def test_dependency_screen_close_restores_last_viewed_wbs_selection() -> None:
    """AC-3: returning from dependency exploration restores a meaningful
    WBS selection (the item most recently jumped to/inspected)."""
    package = build_package_with_relationships()
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        tree.cursor_line = 1  # WP-1.1.1, under "foundation".
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DependencyScreen)
        options = screen.query_one("#dep-options", OptionList)

        option_id = next(
            option_id
            for option_id, neighbor_id in screen._targets.items()
            if neighbor_id == "WP-1.2.2"
        )
        options.highlighted = options.get_option_index(option_id)
        options.action_select()
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, DependencyScreen)
        detail = app.query_one("#detail")
        assert "WP-1.2.2" in detail.text
        assert "Item details" in detail.text
        assert tree.cursor_node.data.work_package.id == "WP-1.2.2"
        assert app.focused is tree


@pytest.mark.asyncio
async def test_dependency_screen_shows_explicit_empty_state_for_isolated_work_package() -> (
    None
):
    """AC-4: a work package with no prerequisites or dependents gets an
    explicit empty state, not an error or blank screen."""
    package = build_package()  # No dependencies at all in this fixture.
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        tree.cursor_line = 1  # WP-1.1.2, under "foundation".
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DependencyScreen)
        header = screen.query_one("#dep-header")
        assert "No dependencies" in header.text

        options = screen.query_one("#dep-options", OptionList)
        rendered = " ".join(str(option.prompt) for option in options.options)
        assert "(none)" in rendered


@pytest.mark.asyncio
async def test_dependency_screen_shows_explicit_empty_state_for_isolated_workstream() -> (
    None
):
    """AC-4: a workstream with no incoming or outgoing edges gets an
    explicit empty state, not an error or blank screen."""
    package = build_package()  # No dependencies at all in this fixture.
    app = PlanApp(package)
    async with app.run_test() as pilot:
        tree = app.query_one(WBSTree)
        tree.cursor_line = 0  # "foundation" workstream.
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DependencyScreen)
        header = screen.query_one("#dep-header")
        assert "No dependencies" in header.text
