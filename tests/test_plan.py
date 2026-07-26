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


# --- Graph indexes and validation (WP-1.1.2) ------------------------------


def test_loader_builds_deterministic_prerequisite_and_dependent_graph_indexes(
    tmp_path: Path,
):
    plan_path = _write_plan(tmp_path)

    package = load_execution_package(plan_path)

    first = next(wp for wp in package.work_packages if wp.id == "WP-1.1")
    second = next(wp for wp in package.work_packages if wp.id == "WP-1.2")

    assert first.prerequisites == ()
    assert len(first.dependents) == 1
    dependent_edge = first.dependents[0]
    assert dependent_edge.package_id == "WP-1.2"
    assert dependent_edge.type == "interface"
    assert dependent_edge.reason == "The TUI renders the loader's normalized model."

    assert second.dependents == ()
    assert len(second.prerequisites) == 1
    prerequisite_edge = second.prerequisites[0]
    assert prerequisite_edge.package_id == "WP-1.1"
    assert prerequisite_edge.type == "interface"
    assert prerequisite_edge.reason == "The TUI renders the loader's normalized model."


def test_loader_rolls_up_cross_workstream_graph_edges_onto_workstreams(tmp_path: Path):
    plan_path = _write_plan(tmp_path)

    package = load_execution_package(plan_path)

    model_ws = next(ws for ws in package.workstreams if ws.id == "model")
    tui_ws = next(ws for ws in package.workstreams if ws.id == "tui")

    assert model_ws.incoming == ()
    assert len(model_ws.outgoing) == 1
    assert model_ws.outgoing[0].workstream_id == "tui"
    assert model_ws.outgoing[0].type == "interface"

    assert tui_ws.outgoing == ()
    assert len(tui_ws.incoming) == 1
    assert tui_ws.incoming[0].workstream_id == "model"
    assert tui_ws.incoming[0].type == "interface"


def test_loader_gives_isolated_work_package_empty_graph_indexes(tmp_path: Path):
    (tmp_path / "tasks").mkdir(parents=True)
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
    (tmp_path / "tasks" / "first.toml").write_text(FIRST_TASK_TOML)

    package = load_execution_package(plan_path)

    first = package.work_packages[0]
    assert first.prerequisites == ()
    assert first.dependents == ()
    model_ws = package.workstreams[0]
    assert model_ws.incoming == ()
    assert model_ws.outgoing == ()


def test_loader_rejects_duplicate_workstream_ids_validation(tmp_path: Path):
    (tmp_path / "tasks").mkdir(parents=True)
    plan_path = tmp_path / "plan.toml"
    plan_path.write_text(
        """
version = 1
title = "Sample"

[[workstreams]]
id = "model"
title = "Model"
ownership = []

[[workstreams]]
id = "model"
title = "Model again"
ownership = []
"""
    )

    with pytest.raises(PlanLoadError, match="duplicate workstream id 'model'"):
        load_execution_package(plan_path)


def test_loader_rejects_duplicate_work_package_ids_validation(tmp_path: Path):
    (tmp_path / "tasks").mkdir(parents=True)
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

[[work_packages]]
id = "WP-1.1"
wbs = "1.2"
task = "tasks/first.toml"
workstream = "model"
"""
    )
    (tmp_path / "tasks" / "first.toml").write_text(FIRST_TASK_TOML)

    with pytest.raises(PlanLoadError, match="duplicate work package id 'WP-1.1'"):
        load_execution_package(plan_path)


def test_loader_rejects_work_package_referencing_unknown_workstream_validation(
    tmp_path: Path,
):
    (tmp_path / "tasks").mkdir(parents=True)
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
workstream = "ghost"
"""
    )
    (tmp_path / "tasks" / "first.toml").write_text(FIRST_TASK_TOML)

    with pytest.raises(
        PlanLoadError,
        match="work package 'WP-1.1' references unknown workstream 'ghost'",
    ):
        load_execution_package(plan_path)


def test_loader_rejects_task_contract_id_mismatch_validation(tmp_path: Path):
    (tmp_path / "tasks").mkdir(parents=True)
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
    mismatched_task = FIRST_TASK_TOML.replace('id = "WP-1.1"', 'id = "WP-9.9"')
    (tmp_path / "tasks" / "first.toml").write_text(mismatched_task)

    with pytest.raises(
        PlanLoadError,
        match="work package 'WP-1.1'.*task contract.*id 'WP-9.9' does not match",
    ):
        load_execution_package(plan_path)


def test_loader_rejects_dependency_with_unknown_predecessor_validation(tmp_path: Path):
    plan_path = _write_plan(tmp_path)
    text = plan_path.read_text().replace(
        'predecessor = "WP-1.1"', 'predecessor = "WP-9.9"'
    )
    plan_path.write_text(text)

    with pytest.raises(PlanLoadError, match="unknown predecessor work package 'WP-9.9'"):
        load_execution_package(plan_path)


def test_loader_rejects_dependency_with_unknown_successor_validation(tmp_path: Path):
    plan_path = _write_plan(tmp_path)
    text = plan_path.read_text().replace('successor = "WP-1.2"', 'successor = "WP-9.9"')
    plan_path.write_text(text)

    with pytest.raises(PlanLoadError, match="unknown successor work package 'WP-9.9'"):
        load_execution_package(plan_path)


def test_loader_rejects_unsupported_dependency_type_validation(tmp_path: Path):
    plan_path = _write_plan(tmp_path)
    text = plan_path.read_text().replace('type = "interface"', 'type = "vibes"')
    plan_path.write_text(text)

    with pytest.raises(PlanLoadError, match="unsupported dependency type 'vibes'"):
        load_execution_package(plan_path)


def test_loader_rejects_dependency_cycle_validation(tmp_path: Path):
    plan_path = _write_plan(tmp_path)
    text = plan_path.read_text() + (
        "\n[[dependencies]]\n"
        'predecessor = "WP-1.2"\n'
        'successor = "WP-1.1"\n'
        'type = "hard"\n'
        'reason = "Manufactured cycle for the test."\n'
    )
    plan_path.write_text(text)

    with pytest.raises(PlanLoadError, match="dependency cycle detected"):
        load_execution_package(plan_path)
