"""Typed models and loader for Meeseeks execution packages.

An execution package is a `plan.toml` plus the task-contract TOML files it
references. This module normalizes both into one read-only in-memory model:
workstreams, WBS-ordered work packages (each carrying its full task
contract), and dependencies. It performs no writes and no graph analysis —
prerequisite/dependent indexes and cross-file validation are built on top of
this model separately.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SUPPORTED_PLAN_VERSION = 1
SUPPORTED_TASK_VERSION = 1


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
class Workstream:
    id: str
    title: str
    ownership: tuple[str, ...]


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

    return ExecutionPackage(
        version=version,
        title=title,
        path=plan_path,
        workstreams=workstreams,
        work_packages=work_packages,
        dependencies=dependencies,
    )


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
