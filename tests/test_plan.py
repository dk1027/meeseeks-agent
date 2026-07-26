"""Tests for the execution-package loader in `meeseeks.plan`."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from meeseeks.plan import PlanLoadError, load_execution_package

PLAN_TOML = """
version = 1
title = "Sample plan"

[[workstreams]]
id = "model"
title = "Model workstream"
ownership = ["src/pkg/**"]

[[workstreams]]
id = "tui"
title = "TUI workstream"
ownership = ["src/tui/**"]

[[work_packages]]
id = "WP-1.2"
wbs = "1.2"
task = "tasks/second.toml"
workstream = "tui"

[[work_packages]]
id = "WP-1.1"
wbs = "1.1"
task = "tasks/first.toml"
workstream = "model"

[[dependencies]]
predecessor = "WP-1.1"
successor = "WP-1.2"
type = "interface"
reason = "The TUI renders the loader's normalized model."
"""

FIRST_TASK_TOML = """
version = 1
id = "WP-1.1"
title = "First task"
description = "Do the first thing."
out_of_scope = ["Doing the second thing"]

[[acceptance_criteria]]
id = "AC-1"
description = "The first thing is done."

[[acceptance_criteria]]
id = "AC-2"
description = "Nothing else changed."

[verification]
commands = ["pytest tests/test_first.py"]
"""

SECOND_TASK_TOML = """
version = 1
id = "WP-1.2"
title = "Second task"
description = "Do the second thing."

[[acceptance_criteria]]
id = "AC-1"
description = "The second thing is done."

[verification]
commands = []
"""


def _write_plan(root: Path) -> Path:
    (root / "tasks").mkdir(parents=True)
    plan_path = root / "plan.toml"
    plan_path.write_text(PLAN_TOML)
    (root / "tasks" / "first.toml").write_text(FIRST_TASK_TOML)
    (root / "tasks" / "second.toml").write_text(SECOND_TASK_TOML)
    return plan_path


def test_loader_loads_valid_plan_and_tasks_into_typed_models(tmp_path: Path):
    plan_path = _write_plan(tmp_path)

    package = load_execution_package(plan_path)

    assert package.version == 1
    assert package.title == "Sample plan"
    assert [ws.id for ws in package.workstreams] == ["model", "tui"]
    assert package.workstreams[0].ownership == ("src/pkg/**",)
    assert len(package.dependencies) == 1
    dep = package.dependencies[0]
    assert (dep.predecessor, dep.successor, dep.type) == ("WP-1.1", "WP-1.2", "interface")
    assert dep.reason == "The TUI renders the loader's normalized model."


def test_loader_orders_work_packages_by_wbs_regardless_of_declaration_order(
    tmp_path: Path,
):
    plan_path = _write_plan(tmp_path)

    package = load_execution_package(plan_path)

    assert [wp.id for wp in package.work_packages] == ["WP-1.1", "WP-1.2"]


def test_loader_preserves_complete_task_contract_without_semantic_loss(tmp_path: Path):
    plan_path = _write_plan(tmp_path)

    package = load_execution_package(plan_path)

    first = next(wp for wp in package.work_packages if wp.id == "WP-1.1")
    assert first.wbs == "1.1"
    assert first.workstream_id == "model"
    assert first.task.title == "First task"
    assert first.task.description == "Do the first thing."
    assert first.task.out_of_scope == ("Doing the second thing",)
    assert [ac.id for ac in first.task.acceptance_criteria] == ["AC-1", "AC-2"]
    assert first.task.verification_commands == ("pytest tests/test_first.py",)


def test_loader_resolves_task_paths_relative_to_plan_directory_not_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    project_dir = tmp_path / "project"
    plan_path = _write_plan(project_dir)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    package = load_execution_package(plan_path)

    first = next(wp for wp in package.work_packages if wp.id == "WP-1.1")
    assert first.task_path == plan_path.parent / "tasks" / "first.toml"
    assert first.task.description == "Do the first thing."


def test_loader_does_not_modify_plan_or_task_files(tmp_path: Path):
    plan_path = _write_plan(tmp_path)
    files = [plan_path, tmp_path / "tasks" / "first.toml", tmp_path / "tasks" / "second.toml"]
    before = {f: (f.read_bytes(), os.stat(f).st_mtime_ns) for f in files}

    load_execution_package(plan_path)

    after = {f: (f.read_bytes(), os.stat(f).st_mtime_ns) for f in files}
    assert before == after


def test_loader_rejects_missing_plan_file(tmp_path: Path):
    with pytest.raises(PlanLoadError, match="file not found"):
        load_execution_package(tmp_path / "missing.toml")


def test_loader_rejects_malformed_plan_toml(tmp_path: Path):
    plan_path = tmp_path / "plan.toml"
    plan_path.write_text("this is not [ valid toml")

    with pytest.raises(PlanLoadError, match="invalid TOML"):
        load_execution_package(plan_path)


def test_loader_rejects_unsupported_plan_version(tmp_path: Path):
    plan_path = tmp_path / "plan.toml"
    plan_path.write_text('version = 2\ntitle = "x"\n')

    with pytest.raises(PlanLoadError, match="unsupported plan version"):
        load_execution_package(plan_path)


def test_loader_rejects_plan_missing_required_field(tmp_path: Path):
    plan_path = tmp_path / "plan.toml"
    plan_path.write_text("version = 1\n")

    with pytest.raises(PlanLoadError, match="missing required field 'title'"):
        load_execution_package(plan_path)


def test_loader_rejects_missing_referenced_task_file(tmp_path: Path):
    plan_path = tmp_path / "plan.toml"
    plan_path.write_text(
        """
version = 1
title = "Sample"

[[workstreams]]
id = "model"
title = "Model"
ownership = []

[[work_packages]]
id = "WP-1.1"
wbs = "1.1"
task = "tasks/missing.toml"
workstream = "model"
"""
    )

    with pytest.raises(PlanLoadError, match="file not found"):
        load_execution_package(plan_path)


def test_loader_rejects_malformed_task_contract(tmp_path: Path):
    (tmp_path / "tasks").mkdir()
    plan_path = tmp_path / "plan.toml"
    plan_path.write_text(
        """
version = 1
title = "Sample"

[[workstreams]]
id = "model"
title = "Model"
ownership = []

[[work_packages]]
id = "WP-1.1"
wbs = "1.1"
task = "tasks/first.toml"
workstream = "model"
"""
    )
    (tmp_path / "tasks" / "first.toml").write_text("version = 1\nid = \"WP-1.1\"\n")

    with pytest.raises(PlanLoadError, match="missing required field 'title'"):
        load_execution_package(plan_path)
