"""Shared text rendering for workstream and work-package detail content.

Both the main detail pane (`meeseeks.plan_tui.app`) and the focused
dependency-explorer screen (`meeseeks.plan_tui.screens`) need to render the
same "full detail" text for a workstream or work package, so it lives here
rather than being duplicated or creating an import cycle between those two
modules.
"""

from __future__ import annotations

from rich.markup import escape

from textual.widgets import Static

from meeseeks.plan import (
    DependencyEdge,
    ExecutionPackage,
    WorkPackage,
    Workstream,
    WorkstreamEdge,
)

WELCOME_TEXT = "Select a workstream or work package to inspect it here."


class TextPane(Static):
    """A `Static` that tracks its current plain-text content on `.text`.

    Textual's `Static` keeps its renderable internally, which is awkward to
    assert on directly from tests. Subclasses (the main detail pane, the
    dependency-explorer header) mirror whatever is passed to `update()` onto
    a plain string attribute instead.
    """

    text: str = ""

    def update(self, content: str = "", *, layout: bool = True) -> None:  # type: ignore[override]
        self.text = content
        super().update(content, layout=layout)


def render_workstream(workstream: Workstream, package: ExecutionPackage) -> str:
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
    lines.extend(render_workstream_edges(workstream.incoming))

    lines.append("")
    lines.append("[b]Outgoing[/b]")
    lines.extend(render_workstream_edges(workstream.outgoing))

    return "\n".join(lines)


def render_workstream_edges(edges: tuple[WorkstreamEdge, ...]) -> list[str]:
    if not edges:
        return ["  (none)"]
    return [
        f"  - {escape(edge.workstream_id)}  [{escape(edge.type)}]  {escape(edge.reason)}"
        for edge in edges
    ]


def render_work_package(work_package: WorkPackage) -> str:
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
    lines.extend(render_dependency_edges(work_package.prerequisites))

    lines.append("")
    lines.append("[b]Dependents[/b]")
    lines.extend(render_dependency_edges(work_package.dependents))

    return "\n".join(lines)


def render_dependency_edges(edges: tuple[DependencyEdge, ...]) -> list[str]:
    if not edges:
        return ["  (none)"]
    return [
        f"  - {escape(edge.package_id)}  [{escape(edge.type)}]  {escape(edge.reason)}"
        for edge in edges
    ]
