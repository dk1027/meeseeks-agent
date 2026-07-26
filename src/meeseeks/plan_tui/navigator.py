"""The collapsible WBS navigator: a `Tree` grouping work packages by workstream.

Work packages are rendered in the order the model already provides (WBS
order, per `meeseeks.plan.load_execution_package`); this module does no
sorting of its own.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.binding import Binding
from textual.widgets import Tree

from meeseeks.plan import ExecutionPackage, WorkPackage, Workstream


@dataclass(frozen=True)
class WorkstreamNode:
    """Tree node payload for a workstream row."""

    workstream: Workstream


@dataclass(frozen=True)
class WorkPackageNode:
    """Tree node payload for a work-package row."""

    work_package: WorkPackage


NodeData = WorkstreamNode | WorkPackageNode


class WBSTree(Tree[NodeData]):
    """WBS navigator tree.

    Adds `j`/`k` as documented alternatives to `up`/`down` (already bound by
    `Tree` itself). `enter` (Tree's built-in `select_cursor` binding) expands
    or collapses workstream rows and posts a `Tree.NodeSelected` message for
    the app to use when inspecting a work package.
    """

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self, package: ExecutionPackage, **kwargs: object) -> None:
        super().__init__(package.title, **kwargs)
        self.show_root = False
        self._populate(package)

    def _populate(self, package: ExecutionPackage) -> None:
        packages_by_workstream: dict[str, list[WorkPackage]] = {
            workstream.id: [] for workstream in package.workstreams
        }
        for work_package in package.work_packages:
            packages_by_workstream.setdefault(work_package.workstream_id, []).append(
                work_package
            )

        for workstream in package.workstreams:
            workstream_node = self.root.add(
                f"{workstream.id}  {workstream.title}",
                data=WorkstreamNode(workstream=workstream),
                expand=True,
            )
            for work_package in packages_by_workstream.get(workstream.id, []):
                workstream_node.add_leaf(
                    f"{work_package.wbs}  {work_package.id}  {work_package.task.title}",
                    data=WorkPackageNode(work_package=work_package),
                )

        self.root.expand()
