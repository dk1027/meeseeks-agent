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

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Tree

from meeseeks.plan import ExecutionPackage
from meeseeks.plan_tui.navigator import NodeData, WBSTree, WorkPackageNode, WorkstreamNode
from meeseeks.plan_tui.render import (
    WELCOME_TEXT,
    TextPane,
    render_work_package,
    render_workstream,
)
from meeseeks.plan_tui.screens import DependencyScreen, HelpScreen


class DetailPane(TextPane):
    """The selected-item pane."""

    text: str = WELCOME_TEXT


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
        ("d", "open_dependencies", "Dependencies"),
        ("question_mark", "show_help", "Help"),
    ]

    def __init__(self, package: ExecutionPackage) -> None:
        super().__init__()
        self._package = package
        self.sub_title = package.title
        self._selected: NodeData | None = None

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
        if isinstance(data, (WorkstreamNode, WorkPackageNode)):
            self._show_detail(data)

    def _show_detail(self, data: NodeData) -> None:
        self._selected = data
        detail = self.query_one("#detail", DetailPane)
        if isinstance(data, WorkstreamNode):
            detail.update(render_workstream(data.workstream, self._package))
        elif isinstance(data, WorkPackageNode):
            detail.update(render_work_package(data.work_package))

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_open_dependencies(self) -> None:
        tree = self.query_one("#navigator", WBSTree)
        node = tree.cursor_node
        if node is None or not isinstance(node.data, (WorkstreamNode, WorkPackageNode)):
            return

        def _on_dismiss(result: NodeData | None) -> None:
            if result is not None:
                self._restore_selection(result)

        self.push_screen(DependencyScreen(node.data, self._package), _on_dismiss)

    def _restore_selection(self, data: NodeData) -> None:
        """Restore a meaningful WBS selection after dependency exploration.

        Finds the tree node matching `data`'s identity (a workstream or work
        package the user most recently jumped to or inspected in the
        dependency screen), moves the navigator cursor there, refreshes the
        detail pane to match, and returns keyboard focus to the tree.
        """
        tree = self.query_one("#navigator", WBSTree)
        target_line = _find_node_line(tree, data)
        if target_line is not None and target_line >= 0:
            tree.cursor_line = target_line
        self._show_detail(data)
        tree.focus()


def _find_node_line(tree: WBSTree, data: NodeData) -> int | None:
    """Return the cursor line of the tree node whose identity matches `data`."""
    target_id = (
        data.workstream.id if isinstance(data, WorkstreamNode) else data.work_package.id
    )

    def walk(node: object) -> int | None:
        node_data = node.data  # type: ignore[attr-defined]
        if isinstance(node_data, WorkstreamNode) and isinstance(data, WorkstreamNode):
            if node_data.workstream.id == target_id:
                return node.line  # type: ignore[attr-defined]
        elif isinstance(node_data, WorkPackageNode) and isinstance(data, WorkPackageNode):
            if node_data.work_package.id == target_id:
                return node.line  # type: ignore[attr-defined]
        for child in node.children:  # type: ignore[attr-defined]
            found = walk(child)
            if found is not None:
                return found
        return None

    return walk(tree.root)
