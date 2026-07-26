"""Typed models and loader for Meeseeks execution packages.

An execution package is a `plan.toml` plus the task-contract TOML files it
references. This module normalizes both into one read-only in-memory model:
workstreams, WBS-ordered work packages (each carrying its full task
contract), and dependencies. It performs no writes. Cross-file validation
(unique IDs, known references, matching task IDs, supported dependency
types, acyclicity) and graph indexes (per-package prerequisite/dependent
collections, per-workstream incoming/outgoing rollups) are derived once at
load time so consumers such as a TUI never re-infer graph relationships
themselves.
"""

from __future__ import annotations

import tomllib
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

SUPPORTED_PLAN_VERSION = 1
SUPPORTED_TASK_VERSION = 1
SUPPORTED_DEPENDENCY_TYPES = frozenset(
    {"hard", "interface", "decision", "environment", "preferred", "integration"}
)


class PlanLoadError(Exception):
    """Raised when a plan or one of its referenced task contracts is invalid.

    The message always names the offending file and field so the CLI can
    report an actionable error before entering the TUI.
    """


@dataclass(frozen=True)
class AcceptanceCriterion:
    id: str
    description: str


@dataclass(frozen=True)
class TaskContract:
    """A fully parsed task-contract TOML file."""

    version: int
    id: str
    title: str
    description: str
    out_of_scope: tuple[str, ...]
    acceptance_criteria: tuple[AcceptanceCriterion, ...]
    verification_commands: tuple[str, ...]
    path: Path


@dataclass(frozen=True)
class DependencyEdge:
    """One end of a dependency, from the perspective of a work package.

    `package_id` names the *other* work package in the relationship (the
    prerequisite when this edge appears in a package's `dependents`
    collection is nonsensical to restate, so callers read `package_id` as
    "the neighbor"), alongside the dependency's type and reason.
    """

    package_id: str
    type: str
    reason: str


@dataclass(frozen=True)
class WorkstreamEdge:
    """A cross-workstream dependency, rolled up for overview presentation."""

    workstream_id: str
    type: str
    reason: str


@dataclass(frozen=True)
class Workstream:
    id: str
    title: str
    ownership: tuple[str, ...]
    incoming: tuple[WorkstreamEdge, ...] = ()
    outgoing: tuple[WorkstreamEdge, ...] = ()


@dataclass(frozen=True)
class Dependency:
    predecessor: str
    successor: str
    type: str
    reason: str


@dataclass(frozen=True)
class WorkPackage:
    """A work package as declared in the plan, joined with its task contract."""

    id: str
    wbs: str
    workstream_id: str
    task_path: Path
    task: TaskContract
    prerequisites: tuple[DependencyEdge, ...] = ()
    dependents: tuple[DependencyEdge, ...] = ()


@dataclass(frozen=True)
class ExecutionPackage:
    """The complete, normalized plan: workstreams, work packages, dependencies."""

    version: int
    title: str
    path: Path
    workstreams: tuple[Workstream, ...]
    work_packages: tuple[WorkPackage, ...]
    dependencies: tuple[Dependency, ...]


def load_execution_package(plan_path: Path | str) -> ExecutionPackage:
    """Load and normalize a version 1 execution package.

    `plan_path` is the path to `plan.toml`. Every task path referenced by
    the plan is resolved relative to `plan_path`'s directory (not the
    process working directory) and parsed as a task contract. Raises
    `PlanLoadError` with an actionable message if the plan, or any task it
    references, is missing or malformed. Performs no writes.
    """
    plan_path = Path(plan_path)
    plan_table = _load_toml(plan_path, context=str(plan_path))
    plan_dir = plan_path.parent

    version = _require(plan_table, "version", plan_path, "plan")
    if version != SUPPORTED_PLAN_VERSION:
        raise PlanLoadError(
            f"{plan_path}: unsupported plan version {version!r} "
            f"(expected {SUPPORTED_PLAN_VERSION})"
        )
    title = _require(plan_table, "title", plan_path, "plan")

    workstreams = tuple(
        _load_workstream(entry, plan_path, index)
        for index, entry in enumerate(plan_table.get("workstreams", []))
    )

    work_packages = tuple(
        _load_work_package(entry, plan_dir, plan_path, index)
        for index, entry in enumerate(plan_table.get("work_packages", []))
    )
    work_packages = tuple(sorted(work_packages, key=lambda wp: _wbs_sort_key(wp.wbs)))

    dependencies = tuple(
        _load_dependency(entry, plan_path, index)
        for index, entry in enumerate(plan_table.get("dependencies", []))
    )

    _validate_graph(plan_path, workstreams, work_packages, dependencies)
    workstreams, work_packages = _index_graph(workstreams, work_packages, dependencies)

    return ExecutionPackage(
        version=version,
        title=title,
        path=plan_path,
        workstreams=workstreams,
        work_packages=work_packages,
        dependencies=dependencies,
    )


def _validate_graph(
    plan_path: Path,
    workstreams: tuple[Workstream, ...],
    work_packages: tuple[WorkPackage, ...],
    dependencies: tuple[Dependency, ...],
) -> None:
    """Validate cross-referential and graph-level invariants.

    Structural per-file validation (missing fields, bad TOML, unsupported
    versions) already happened while loading each object; this checks the
    invariants that only make sense once the whole plan is assembled:
    unique IDs, known references, matching task IDs, supported dependency
    types, and an acyclic dependency graph.
    """
    seen_workstream_ids: set[str] = set()
    for ws in workstreams:
        if ws.id in seen_workstream_ids:
            raise PlanLoadError(f"{plan_path}: duplicate workstream id {ws.id!r}")
        seen_workstream_ids.add(ws.id)

    seen_package_ids: set[str] = set()
    for wp in work_packages:
        if wp.id in seen_package_ids:
            raise PlanLoadError(f"{plan_path}: duplicate work package id {wp.id!r}")
        seen_package_ids.add(wp.id)

        if wp.workstream_id not in seen_workstream_ids:
            raise PlanLoadError(
                f"{plan_path}: work package {wp.id!r} references unknown "
                f"workstream {wp.workstream_id!r}"
            )

        if wp.task.id != wp.id:
            raise PlanLoadError(
                f"{plan_path}: work package {wp.id!r} references task contract "
                f"{wp.task_path} whose id {wp.task.id!r} does not match"
            )

    for index, dep in enumerate(dependencies):
        context = f"{plan_path}: dependencies[{index}]"
        if dep.predecessor not in seen_package_ids:
            raise PlanLoadError(
                f"{context}: unknown predecessor work package {dep.predecessor!r}"
            )
        if dep.successor not in seen_package_ids:
            raise PlanLoadError(
                f"{context}: unknown successor work package {dep.successor!r}"
            )
        if dep.type not in SUPPORTED_DEPENDENCY_TYPES:
            raise PlanLoadError(
                f"{context}: unsupported dependency type {dep.type!r} "
                f"(expected one of {sorted(SUPPORTED_DEPENDENCY_TYPES)})"
            )

    _check_acyclic(plan_path, seen_package_ids, dependencies)


def _check_acyclic(
    plan_path: Path, package_ids: set[str], dependencies: tuple[Dependency, ...]
) -> None:
    successors: dict[str, list[str]] = defaultdict(list)
    for dep in dependencies:
        successors[dep.predecessor].append(dep.successor)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {package_id: WHITE for package_id in package_ids}

    def visit(node: str, path: list[str]) -> None:
        color[node] = GRAY
        path.append(node)
        for neighbor in successors.get(node, []):
            if color[neighbor] == GRAY:
                cycle = path[path.index(neighbor) :] + [neighbor]
                raise PlanLoadError(
                    f"{plan_path}: dependency cycle detected: {' -> '.join(cycle)}"
                )
            if color[neighbor] == WHITE:
                visit(neighbor, path)
        path.pop()
        color[node] = BLACK

    for package_id in sorted(package_ids):
        if color[package_id] == WHITE:
            visit(package_id, [])


def _index_graph(
    workstreams: tuple[Workstream, ...],
    work_packages: tuple[WorkPackage, ...],
    dependencies: tuple[Dependency, ...],
) -> tuple[tuple[Workstream, ...], tuple[WorkPackage, ...]]:
    """Derive per-package prerequisite/dependent and per-workstream rollup indexes.

    Runs once at load time so the TUI (or any other consumer) reads
    precomputed, deterministic collections instead of inferring graph
    relationships itself.
    """
    workstream_by_package = {wp.id: wp.workstream_id for wp in work_packages}

    prerequisites: dict[str, list[DependencyEdge]] = defaultdict(list)
    dependents: dict[str, list[DependencyEdge]] = defaultdict(list)
    outgoing: dict[str, list[WorkstreamEdge]] = defaultdict(list)
    incoming: dict[str, list[WorkstreamEdge]] = defaultdict(list)

    for dep in dependencies:
        dependents[dep.predecessor].append(
            DependencyEdge(package_id=dep.successor, type=dep.type, reason=dep.reason)
        )
        prerequisites[dep.successor].append(
            DependencyEdge(package_id=dep.predecessor, type=dep.type, reason=dep.reason)
        )

        predecessor_ws = workstream_by_package[dep.predecessor]
        successor_ws = workstream_by_package[dep.successor]
        if predecessor_ws != successor_ws:
            outgoing[predecessor_ws].append(
                WorkstreamEdge(workstream_id=successor_ws, type=dep.type, reason=dep.reason)
            )
            incoming[successor_ws].append(
                WorkstreamEdge(workstream_id=predecessor_ws, type=dep.type, reason=dep.reason)
            )

    def sort_key(edge: DependencyEdge | WorkstreamEdge) -> tuple[str, str, str]:
        neighbor = edge.package_id if isinstance(edge, DependencyEdge) else edge.workstream_id
        return (neighbor, edge.type, edge.reason)

    indexed_work_packages = tuple(
        replace(
            wp,
            prerequisites=tuple(sorted(prerequisites.get(wp.id, []), key=sort_key)),
            dependents=tuple(sorted(dependents.get(wp.id, []), key=sort_key)),
        )
        for wp in work_packages
    )

    indexed_workstreams = tuple(
        replace(
            ws,
            incoming=tuple(sorted(incoming.get(ws.id, []), key=sort_key)),
            outgoing=tuple(sorted(outgoing.get(ws.id, []), key=sort_key)),
        )
        for ws in workstreams
    )

    return indexed_workstreams, indexed_work_packages


def _load_workstream(entry: dict[str, Any], plan_path: Path, index: int) -> Workstream:
    context = f"{plan_path}: workstreams[{index}]"
    return Workstream(
        id=_require(entry, "id", plan_path, context),
        title=_require(entry, "title", plan_path, context),
        ownership=tuple(entry.get("ownership", [])),
    )


def _load_work_package(
    entry: dict[str, Any], plan_dir: Path, plan_path: Path, index: int
) -> WorkPackage:
    context = f"{plan_path}: work_packages[{index}]"
    package_id = _require(entry, "id", plan_path, context)
    wbs = _require(entry, "wbs", plan_path, context)
    workstream_id = _require(entry, "workstream", plan_path, context)
    raw_task_path = _require(entry, "task", plan_path, context)

    task_path = plan_dir / raw_task_path
    task = _load_task_contract(task_path, referenced_by=package_id)

    return WorkPackage(
        id=package_id,
        wbs=wbs,
        workstream_id=workstream_id,
        task_path=task_path,
        task=task,
    )


def _load_dependency(entry: dict[str, Any], plan_path: Path, index: int) -> Dependency:
    context = f"{plan_path}: dependencies[{index}]"
    return Dependency(
        predecessor=_require(entry, "predecessor", plan_path, context),
        successor=_require(entry, "successor", plan_path, context),
        type=_require(entry, "type", plan_path, context),
        reason=_require(entry, "reason", plan_path, context),
    )


def _load_task_contract(task_path: Path, *, referenced_by: str) -> TaskContract:
    context = f"{task_path} (referenced by {referenced_by})"
    table = _load_toml(task_path, context=context)

    version = _require(table, "version", task_path, context)
    if version != SUPPORTED_TASK_VERSION:
        raise PlanLoadError(
            f"{context}: unsupported task version {version!r} "
            f"(expected {SUPPORTED_TASK_VERSION})"
        )

    acceptance_criteria = tuple(
        AcceptanceCriterion(
            id=_require(ac, "id", task_path, f"{context}: acceptance_criteria[{i}]"),
            description=_require(
                ac, "description", task_path, f"{context}: acceptance_criteria[{i}]"
            ),
        )
        for i, ac in enumerate(table.get("acceptance_criteria", []))
    )

    verification = table.get("verification", {})

    return TaskContract(
        version=version,
        id=_require(table, "id", task_path, context),
        title=_require(table, "title", task_path, context),
        description=_require(table, "description", task_path, context),
        out_of_scope=tuple(table.get("out_of_scope", [])),
        acceptance_criteria=acceptance_criteria,
        verification_commands=tuple(verification.get("commands", [])),
        path=task_path,
    )


def _load_toml(path: Path, *, context: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise PlanLoadError(f"{context}: file not found") from exc
    except OSError as exc:
        raise PlanLoadError(f"{context}: could not read file ({exc})") from exc

    try:
        return tomllib.loads(raw.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise PlanLoadError(f"{context}: invalid TOML ({exc})") from exc


def _require(table: dict[str, Any], key: str, path: Path, context: str) -> Any:
    if key not in table:
        raise PlanLoadError(f"{context}: missing required field {key!r}")
    return table[key]


def _wbs_sort_key(wbs: str) -> tuple[int, ...]:
    return tuple(int(part) for part in wbs.split("."))
