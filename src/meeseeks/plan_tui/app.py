"""The Textual application shell for `meeseeks plan`.

`PlanApp` is constructed directly from an already-loaded
`meeseeks.plan.ExecutionPackage` — it never discovers or loads a plan from
disk. That responsibility belongs to the CLI layer that hands this app its
model. This module renders the read-only shell only: a title bar, a
collapsible WBS navigator, a selected-item pane, and a footer with key
hints. Rendering the full task-contract detail (description, acceptance
criteria, dependencies, etc.) in the selected-item pane is later work; this
shell establishes the regions and navigation it will fill in.
"""

from __future__ import annotations

from rich.markup import escape

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Static, Tree

from meeseeks.plan import (
    DependencyEdge,
    ExecutionPackage,
    WorkPackage,
    Workstream,
    WorkstreamEdge,
)
from meeseeks.plan_tui.navigator import WBSTree, WorkPackageNode, WorkstreamNode
from meeseeks.plan_tui.screens import HelpScreen

WELCOME_TEXT = "Select a workstream or work package to inspect it here."


class DetailPane(Static):
    """The selected-item pane.

    Tracks its current plain-text content on `.text` (in addition to the
    renderable Static keeps internally) so tests can assert on it without
    reaching into Textual's private rendering internals.
    """

    text: str = WELCOME_TEXT

    def update(self, content: str = "", *, layout: bool = True) -> None:  # type: ignore[override]
        self.text = content
        super().update(content, layout=layout)


class PlanApp(App[None]):
    """Read-only WBS explorer for a Meeseeks execution package."""

    TITLE = "meeseeks plan"

    CSS = """
    #body {
        height: 1fr;
    }

    #navigator {
        width: 40%;
        border-right: solid $primary;
    }

    #detail-scroll {
        width: 1fr;
    }

    #detail {
        padding: 1 2;
        width: 1fr;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("question_mark", "show_help", "Help"),
    ]

    def __init__(self, package: ExecutionPackage) -> None:
        super().__init__()
        self._package = package
        self.sub_title = package.title

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="body"):
            yield WBSTree(self._package, id="navigator")
            with VerticalScroll(id="detail-scroll"):
                yield DetailPane(WELCOME_TEXT, id="detail")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#navigator", WBSTree).focus()

    def on_tree_node_selected(self, event: Tree.NodeSelected[object]) -> None:
        data = event.node.data
        detail = self.query_one("#detail", DetailPane)
        if isinstance(data, WorkstreamNode):
            detail.update(_render_workstream(data.workstream, self._package))
        elif isinstance(data, WorkPackageNode):
            detail.update(_render_work_package(data.work_package))

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())


def _render_workstream(workstream: Workstream, package: ExecutionPackage) -> str:
    """Render a workstream's identity, ownership, packages, and edge rollups."""
    lines = [
        f"[b]{escape(workstream.id)}[/b]  {escape(workstream.title)}",
        "",
        "[b]Ownership[/b]",
    ]
    if workstream.ownership:
        lines.extend(f"  - {escape(pattern)}" for pattern in workstream.ownership)
    else:
        lines.append("  (none declared)")

    contained = [
        wp for wp in package.work_packages if wp.workstream_id == workstream.id
    ]
    lines.append("")
    lines.append(f"[b]Work packages[/b] ({len(contained)})")
    if contained:
        lines.extend(f"  - {escape(wp.id)}  {escape(wp.task.title)}" for wp in contained)
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("[b]Incoming[/b]")
    lines.extend(_render_workstream_edges(workstream.incoming))

    lines.append("")
    lines.append("[b]Outgoing[/b]")
    lines.extend(_render_workstream_edges(workstream.outgoing))

    return "\n".join(lines)


def _render_workstream_edges(edges: tuple[WorkstreamEdge, ...]) -> list[str]:
    if not edges:
        return ["  (none)"]
    return [
        f"  - {escape(edge.workstream_id)}  [{escape(edge.type)}]  {escape(edge.reason)}"
        for edge in edges
    ]


def _render_work_package(work_package: WorkPackage) -> str:
    """Render every documented task-contract field plus WBS/workstream/graph context."""
    task = work_package.task
    lines = [
        f"[b]{escape(work_package.id)}[/b]  {escape(task.title)}",
        f"WBS: {escape(work_package.wbs)}",
        f"Workstream: {escape(work_package.workstream_id)}",
        f"Task path: {escape(str(work_package.task_path))}",
        "",
        "[b]Description[/b]",
        escape(task.description),
    ]

    lines.append("")
    lines.append("[b]Out of scope[/b]")
    if task.out_of_scope:
        lines.extend(f"  - {escape(item)}" for item in task.out_of_scope)
    else:
        lines.append("  (none declared)")

    lines.append("")
    lines.append("[b]Acceptance criteria[/b]")
    if task.acceptance_criteria:
        lines.extend(
            f"  - {escape(ac.id)}: {escape(ac.description)}"
            for ac in task.acceptance_criteria
        )
    else:
        lines.append("  (none declared)")

    lines.append("")
    lines.append("[b]Verification commands[/b]")
    if task.verification_commands:
        lines.extend(f"  - {escape(cmd)}" for cmd in task.verification_commands)
    else:
        lines.append("  (none declared)")

    lines.append("")
    lines.append("[b]Prerequisites[/b]")
    lines.extend(_render_dependency_edges(work_package.prerequisites))

    lines.append("")
    lines.append("[b]Dependents[/b]")
    lines.extend(_render_dependency_edges(work_package.dependents))

    return "\n".join(lines)


def _render_dependency_edges(edges: tuple[DependencyEdge, ...]) -> list[str]:
    if not edges:
        return ["  (none)"]
    return [
        f"  - {escape(edge.package_id)}  [{escape(edge.type)}]  {escape(edge.reason)}"
        for edge in edges
    ]
