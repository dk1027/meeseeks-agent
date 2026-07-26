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
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static, Tree

from meeseeks.plan import ExecutionPackage
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

    #detail {
        width: 1fr;
        padding: 1 2;
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
            yield DetailPane(WELCOME_TEXT, id="detail")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#navigator", WBSTree).focus()

    def on_tree_node_selected(self, event: Tree.NodeSelected[object]) -> None:
        data = event.node.data
        detail = self.query_one("#detail", DetailPane)
        if isinstance(data, WorkstreamNode):
            workstream = data.workstream
            detail.update(
                f"[b]{workstream.id}[/b]  {workstream.title}\n\n"
                f"Ownership: {', '.join(workstream.ownership) or '(none declared)'}"
            )
        elif isinstance(data, WorkPackageNode):
            work_package = data.work_package
            detail.update(
                f"[b]{work_package.id}[/b]  ({work_package.wbs})\n"
                f"{work_package.task.title}"
            )

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())
