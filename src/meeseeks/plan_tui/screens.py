"""Modal screens for the plan explorer shell."""

from __future__ import annotations

import itertools

from rich.markup import escape

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from meeseeks.plan import DependencyEdge, ExecutionPackage, WorkstreamEdge
from meeseeks.plan_tui.navigator import NodeData, WorkPackageNode, WorkstreamNode
from meeseeks.plan_tui.render import TextPane

HELP_TEXT = """\
[b]Keyboard help[/b]

  up / down, j / k    Move selection
  enter               Expand, collapse, or inspect
  d                   Open dependencies for the selection
  ?                   Show this help
  q                   Quit
  escape               Close this help / dependency view
"""


class HelpScreen(ModalScreen[None]):
    """Contextual help overlay listing the documented key bindings."""

    BINDINGS = [
        Binding("escape", "dismiss_help", "Close", show=False),
        Binding("q", "dismiss_help", "Close", show=False),
        Binding("question_mark", "dismiss_help", "Close", show=False),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > Container {
        width: auto;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    """

    def compose(self):
        with Container():
            yield Static(HELP_TEXT, id="help-text")

    def action_dismiss_help(self) -> None:
        self.dismiss(None)


NO_DEPENDENCIES_TEXT = "No dependencies."


class DependencyScreen(ModalScreen[NodeData | None]):
    """The focused dependency-neighborhood view.

    Lists every incoming/outgoing edge (for a workstream) or
    prerequisite/dependent edge (for a work package) for the item it is
    given, with the neighbor's id, dependency type, and full reason
    (AC-1). Selecting a (non-header, non-empty-placeholder) option jumps to
    that neighbor and re-renders the screen in place with the neighbor's
    own edges, so the user can keep exploring outward from either endpoint
    (AC-2). `escape`/`q` close the screen, returning the most recently
    viewed item so the caller can restore a meaningful WBS selection
    (AC-3). An item with no edges at all in either direction gets an
    explicit "No dependencies." note rather than an empty or broken screen
    (AC-4).
    """

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("q", "close", "Close", show=False),
    ]

    DEFAULT_CSS = """
    DependencyScreen {
        align: center middle;
    }

    DependencyScreen > Container {
        width: 90%;
        height: 90%;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }

    DependencyScreen #dep-header {
        height: auto;
        padding-bottom: 1;
    }

    DependencyScreen #dep-options {
        height: 1fr;
    }

    DependencyScreen #dep-footer {
        height: auto;
        padding-top: 1;
        color: $text-muted;
    }
    """

    def __init__(self, item: NodeData, package: ExecutionPackage) -> None:
        super().__init__()
        self._package = package
        self._item = item
        self._targets: dict[str, str] = {}
        self._neighbor_kind: str = "workstream"

    def compose(self) -> ComposeResult:
        with Container():
            yield TextPane(id="dep-header")
            yield OptionList(id="dep-options")
            yield Static(
                "enter: jump to neighbor    escape / q: back to WBS", id="dep-footer"
            )

    def on_mount(self) -> None:
        self._render_item(self._item)

    def _render_item(self, item: NodeData) -> None:
        self._item = item
        self._targets = {}
        header = self.query_one("#dep-header", TextPane)
        options = self.query_one("#dep-options", OptionList)
        options.clear_options()
        counter = itertools.count()

        if isinstance(item, WorkstreamNode):
            workstream = item.workstream
            self._neighbor_kind = "workstream"
            title = f"[b]{escape(workstream.id)}[/b]  {escape(workstream.title)}"
            has_any = bool(workstream.incoming or workstream.outgoing)
            self._add_workstream_edges(options, counter, "Incoming", workstream.incoming)
            self._add_workstream_edges(options, counter, "Outgoing", workstream.outgoing)
        elif isinstance(item, WorkPackageNode):
            work_package = item.work_package
            self._neighbor_kind = "package"
            title = (
                f"[b]{escape(work_package.id)}[/b]  {escape(work_package.task.title)}"
            )
            has_any = bool(work_package.prerequisites or work_package.dependents)
            self._add_dependency_edges(
                options, counter, "Prerequisites", work_package.prerequisites
            )
            self._add_dependency_edges(
                options, counter, "Dependents", work_package.dependents
            )
        else:  # pragma: no cover - defensive; NodeData is a closed union
            title = ""
            has_any = False

        header_lines = [title]
        if not has_any:
            header_lines.append(f"[i]{NO_DEPENDENCIES_TEXT}[/i]")
        header.update("\n".join(header_lines))

    def _add_workstream_edges(
        self,
        options: OptionList,
        counter: itertools.count,
        label: str,
        edges: tuple[WorkstreamEdge, ...],
    ) -> None:
        options.add_option(Option(f"[b]{label}[/b]", disabled=True))
        if not edges:
            options.add_option(Option("  (none)", disabled=True))
            return
        for edge in edges:
            option_id = f"opt-{next(counter)}"
            self._targets[option_id] = edge.workstream_id
            options.add_option(
                Option(
                    f"  {escape(edge.workstream_id)}  [{escape(edge.type)}]  "
                    f"{escape(edge.reason)}",
                    id=option_id,
                )
            )

    def _add_dependency_edges(
        self,
        options: OptionList,
        counter: itertools.count,
        label: str,
        edges: tuple[DependencyEdge, ...],
    ) -> None:
        options.add_option(Option(f"[b]{label}[/b]", disabled=True))
        if not edges:
            options.add_option(Option("  (none)", disabled=True))
            return
        for edge in edges:
            option_id = f"opt-{next(counter)}"
            self._targets[option_id] = edge.package_id
            options.add_option(
                Option(
                    f"  {escape(edge.package_id)}  [{escape(edge.type)}]  "
                    f"{escape(edge.reason)}",
                    id=option_id,
                )
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        if option_id is None or option_id not in self._targets:
            return
        neighbor_id = self._targets[option_id]
        neighbor = self._find_neighbor(neighbor_id)
        if neighbor is not None:
            self._render_item(neighbor)

    def _find_neighbor(self, neighbor_id: str) -> NodeData | None:
        if self._neighbor_kind == "workstream":
            for workstream in self._package.workstreams:
                if workstream.id == neighbor_id:
                    return WorkstreamNode(workstream=workstream)
            return None
        for work_package in self._package.work_packages:
            if work_package.id == neighbor_id:
                return WorkPackageNode(work_package=work_package)
        return None

    def action_close(self) -> None:
        self.dismiss(self._item)
