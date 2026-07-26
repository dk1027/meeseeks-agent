---
name: meeseeks-wbsify
description: Decompose project or product scope into a deliverable-oriented work breakdown structure, create Meeseeks work-package task TOML contracts, organize them into parallel workstreams, and write a dependency-mapped Meeseeks plan. Use when converting a plan, specification, roadmap, epic, or broad implementation request into agent-executable and independently verifiable Meeseeks tasks; coordinating multiple builder agents; or repairing overlapping, incomplete, or falsely parallel task plans.
---

# Meeseeks WBSify

Convert broad scope into a Meeseeks execution package: `.meeseeks/plan.toml` plus independently verifiable task contracts under `.meeseeks/tasks/`.

## Workflow

### 1. Establish the scope boundary

- Read the supplied plan, specification, repository instructions, and relevant existing implementation.
- State the objective, deliverables, exclusions, constraints, assumptions, and unresolved decisions.
- Resolve low-risk decisions from evidence. Surface choices that materially change scope.
- Preserve the distinction between product scope and the work required to deliver it.

### 2. Build a deliverable-oriented WBS

- Put the project outcome at level 1 and decompose it into deliverables.
- Apply the 100 percent rule: include all required implementation, integration, testing, documentation, migration, security, and enabling work.
- Keep siblings mutually exclusive enough for unambiguous ownership.
- Describe completed outcomes rather than chronological activities.
- Stop when each leaf is assignable, estimable, and independently verifiable as one work package.

Read [references/wbs-quality.md](references/wbs-quality.md) when scope is large, decomposition is contested, or terminology needs clarification.

### 3. Write Meeseeks task contracts

Create one `.meeseeks/tasks/<task-name>.toml` for every leaf work package using this shape:

```toml
version = 1
id = "WP-1.2.3"
title = "Outcome-oriented title"
description = """
Purpose, included behavior, boundaries, inputs, outputs, affected interfaces,
assumptions, and implementation guidance needed by the intended builder.
"""
out_of_scope = ["Explicit exclusion"]

[[acceptance_criteria]]
id = "AC-1"
description = "Observable completion condition."

[verification]
commands = ["deterministic offline verification command"]
```

- Give every work package a unique stable ID derived from its WBS position.
- Keep acceptance-criterion IDs unique within the task.
- Put dependency and workstream metadata in the plan, not in task descriptions.
- Size tasks for the intended builder. For weaker agents, name file boundaries, negative cases, preservation requirements, and deterministic tests.
- Do not infer intended requirements solely from existing behavior. Ask when intent is materially ambiguous.

### 4. Map dependencies

- Map prerequisites between work-package IDs rather than relying on filename or list order.
- Classify each dependency as `hard`, `interface`, `decision`, `environment`, `preferred`, or `integration`.
- State why the dependency exists.
- Replace accidental sequential coupling with stable primitive interfaces where practical.
- Check for cycles. Break them or report the unresolved architectural coupling.

### 5. Form parallel workstreams

- Group packages by cohesive deliverable ownership and minimal coordination.
- Give each stream non-overlapping file, component, or interface ownership.
- Ensure each stream can start with available inputs and verify its output independently.
- Do not call streams independent when one imports another's unfinished implementation. Move the shared prerequisite before the fork or define an agreed interface.
- Reserve shared files and CLI wiring for named integration work packages.

### 6. Write the Meeseeks plan

Write `.meeseeks/plan.toml` with:

- `version = 1` and a title.
- `[[workstreams]]` entries with unique IDs, titles, and ownership patterns.
- `[[work_packages]]` entries with `id`, `wbs`, task path, and workstream ID.
- `[[dependencies]]` entries with predecessor, successor, type, and reason.
- Integration and end-to-end gates represented as ordinary work packages with their own task contracts.

Do not duplicate task descriptions or acceptance criteria in the plan. Task files are verification contracts; the plan is the execution graph.

### 7. Validate the execution package

- Parse every generated TOML file.
- Confirm every task has the required version, stable ID, description, at least one acceptance criterion, and verification command.
- Confirm task IDs and workstream IDs are unique.
- Confirm every plan task path resolves and its task ID matches the plan entry.
- Confirm every dependency endpoint exists and the graph is acyclic.
- Confirm each scoped deliverable maps to exactly one WBS branch or explicit integration package.
- Confirm parallel streams have no undeclared ownership overlap before integration.
- Run `meeseeks verify` only when implementation exists and the user requests verification; generating the plan does not prove tasks complete.

## Output summary

After writing files, report the WBS tree, parallel workstreams, dependency fork/join points, integration gates, open decisions, generated paths, and validation performed.
