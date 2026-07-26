# Plan command

## Summary

`meeseeks plan` is a terminal workspace for understanding and refining a Meeseeks work breakdown structure. It presents the workstreams, work packages, task contracts, and dependency graph produced by `meeseeks-wbsify` without requiring users to read or cross-reference TOML files manually.

The initial release is a read-only explorer. The longer-term product turns the explorer into a planning review loop in which users comment on precise WBS elements, ask Meeseeks to revise the plan, review a semantic diff, and accept a new plan revision.

## Problem

`meeseeks-wbsify` produces an execution package with a plan and many task contracts. The files are suitable for tools and builder agents, but they are cumbersome for a person to review as a whole:

- workstream boundaries are separated from work-package descriptions;
- task details and acceptance criteria live in separate files;
- dependencies are expressed as edge records rather than a navigable graph;
- false parallelism, missing integration work, and oversized packages are difficult to spot;
- reviewing the plan requires repeatedly moving between files and retaining graph context mentally.

A passive diagram would improve comprehension, but the larger opportunity is a durable planning workflow. A user should eventually be able to explore a proposed WBS, attach feedback to the exact object that needs attention, and use that feedback to drive a controlled revision.

## Product principles

1. **Terminal-native.** Planning stays in the repository and beside the user's coding agent. The primary interface is a keyboard-driven TUI.
2. **The execution package remains the source of truth.** The TUI reads `plan.toml` and its referenced task contracts. It does not introduce a second authored representation of the WBS.
3. **Overview before detail.** Users begin with workstreams and major relationships, then progressively disclose work packages, task details, and individual dependencies.
4. **Dependencies are first-class.** The interface must make prerequisites, dependents, dependency types, and reasons explorable rather than treating the WBS as only a tree.
5. **Safe revision.** Future plan changes are proposed and reviewed before files are changed. Comments must never silently mutate execution contracts.
6. **Stable review context.** Future comments and revisions require identities that survive reordering and movement within the WBS.

## Command experience

The primary command is:

```sh
meeseeks plan [PLAN_PATH]
```

If `PLAN_PATH` is omitted, Meeseeks discovers `.meeseeks/plan.toml` from the current project. Supplying a path opens that execution package directly.

The command validates the plan and referenced tasks before opening the TUI. Invalid inputs produce actionable terminal errors that identify the file and field involved. The command never modifies plan or task files in the MVP.

## Information architecture

The main workspace has four regions:

```text
┌─ Plan title ──────────────────────────────────────────────────────┐
│ Overview  Dependencies  Help                                     │
├─ WBS / workstreams ──────────┬─ Selected item ───────────────────┤
│ ▼ Foundation                 │ WP-1.1.2  Task and result models   │
│   ├─ WP-1.1.1 Architecture   │                                    │
│   ├─ WP-1.1.2 Models       ◀ │ Description...                     │
│   └─ WP-1.1.3 Init           │                                    │
│ ▶ Authoring                  │ Acceptance criteria                │
│ ▶ Runtime                    │ Dependencies                       │
│ ▶ Backend                    │ Verification commands              │
├──────────────────────────────┴────────────────────────────────────┤
│ ↑/↓ navigate  Enter expand  d dependencies  ? help  q quit       │
└───────────────────────────────────────────────────────────────────┘
```

### WBS navigator

The navigator groups work packages under their workstreams and orders packages by WBS position. Workstreams can be expanded or collapsed. Each row exposes enough identity to distinguish packages without overwhelming the overview.

Selecting a workstream shows:

- its ID and title;
- ownership patterns;
- package count and contained packages;
- incoming and outgoing workstream relationships derived from package dependencies.

Selecting a work package shows:

- stable package ID and WBS position;
- title and full description loaded from its task contract;
- explicit exclusions;
- acceptance criteria;
- verification commands;
- task file path;
- prerequisites and dependents, including type and reason.

### Dependency exploration

The normal detail pane gives dependency context for the selected object. A focused dependency view provides a larger, navigable representation of the graph.

The focused view must support:

- jumping from an edge to its predecessor or successor;
- distinguishing dependency types;
- reading the reason for an edge;
- filtering to the selected workstream or package neighborhood;
- returning to the prior WBS selection without losing context.

The TUI should favor legible lists and small neighborhood diagrams over attempting to render the entire graph as dense terminal art. A whole-plan graph may be added when it remains readable, but it is not the primary navigation model.

### Keyboard interaction

The interface must be usable without a mouse. Default bindings should follow common terminal conventions and be visible in contextual help:

| Key | Action |
| --- | --- |
| `↑` / `↓`, `j` / `k` | Move selection |
| `Enter` | Expand, collapse, or inspect |
| `d` | Open dependencies for the selection |
| `/` | Search or filter; post-MVP unless inexpensive |
| `?` | Show contextual help |
| `q` | Quit |

Bindings must not interfere with terminal exit behavior, and the interface must remain useful at a conventional 80×24 terminal size.

## Full product vision

The read-only explorer is the foundation for an iterative planning workflow:

```text
Generate WBS → Explore → Comment → Propose revision → Review → Accept
                    ↑                                      │
                    └──────────────────────────────────────┘
```

### Structured comments

Users will be able to attach comments to the plan, a workstream, a work package, a dependency, or an acceptance criterion. Comments may be categorized as general feedback, clarification, scope change, split, merge, missing work, ownership change, dependency change, acceptance-criterion change, risk, or decision.

Discussion state belongs in a separate review artifact rather than in `plan.toml` or task contracts. This preserves the distinction between an executable contract and feedback about that contract.

### Controlled revision

Open comments can be supplied to Meeseeks to propose a revised execution package. The user reviews a semantic diff describing additions, removals, moves, splits, merges, contract changes, and dependency changes. Only accepted changes update the plan and task files. Resolved comments remain linked to the revision that addressed them.

This workflow will require stable identities for packages, dependencies, and criteria across revisions. WBS positions are presentation and decomposition coordinates; they should not be the sole long-lived identity when items can move or be inserted.

### Later overlays

Once plan execution exists, the same workspace may display package state such as ready, blocked, in progress, implemented, verified, incomplete, or inconclusive. Execution controls and status tracking are separate from the planning MVP.

## Read-only explorer MVP

### Objective

Let a user open a valid Meeseeks execution package in the terminal, understand its WBS structure, inspect every work package contract, and explore its dependencies without editing files manually.

### In scope

- `meeseeks plan [PLAN_PATH]` and default `.meeseeks/plan.toml` discovery.
- Typed loading and validation of plan version 1.
- Resolution and validation of every referenced task contract.
- A Textual-based TUI integrated with the existing Typer CLI and Rich output conventions.
- Collapsible workstreams with WBS-ordered work packages.
- Detail views for workstreams and work packages.
- Display of descriptions, exclusions, acceptance criteria, verification commands, ownership, and task paths.
- Package prerequisites and dependents with dependency type and reason.
- A focused dependency-neighborhood view with navigation between related packages.
- Keyboard navigation, contextual help, scrolling, and graceful behavior at 80×24.
- Clear handling of missing, malformed, unsupported, or internally inconsistent execution packages.
- Deterministic tests using checked-in plan and task fixtures, including TUI interaction tests.
- A short README entry documenting how to launch and navigate the explorer.

### Out of scope

- Creating, editing, deleting, or reordering workstreams and work packages.
- Comments, discussion threads, review artifacts, and comment resolution.
- AI-assisted or deterministic plan revision.
- Revision history, semantic diffs, and selective acceptance.
- Multi-user collaboration, identity, permissions, synchronization, or notifications.
- Plan execution, work assignment, scheduling, progress tracking, or verification-status overlays.
- Hosted services, browser interfaces, IDE extensions, and static HTML export.
- Searching or filtering unless it falls out naturally from the chosen TUI widgets.
- Changes to the version 1 plan or task schemas beyond what is required to parse their documented fields.

### Success criteria

The MVP succeeds when a user can:

1. run `meeseeks plan` in a repository containing a valid execution package;
2. see all workstreams and work packages in WBS order;
3. select any package and read its complete task contract;
4. identify all prerequisites and dependents and understand why each dependency exists;
5. navigate between related packages without returning to the filesystem;
6. exit with the plan and task files byte-for-byte unchanged;
7. receive an actionable error instead of a broken TUI when the execution package is invalid.

## Technical direction

- Use Textual for the application shell, focus management, tree navigation, panes, modals, key bindings, and UI tests.
- Keep TOML parsing, path resolution, validation, and graph normalization independent of Textual so other renderers can reuse them later.
- Represent workstreams, packages, and dependencies in a normalized read model. The UI must not repeatedly parse task files or infer graph relationships itself.
- Derive incoming and outgoing indexes once when loading the plan.
- Keep the command read-only. Opening and navigating a plan must perform no writes, including migration or formatting writes.
- Treat task paths as relative to the directory containing the plan, consistent with the execution-package layout.
- Report validation failures before entering the alternate screen and restore the terminal cleanly after runtime errors.

## Risks and open decisions

- Dense dependency graphs may not have a useful whole-plan terminal layout. The MVP addresses this with contextual dependency neighborhoods.
- The repository currently documents one root `.meeseeks/plan.toml`; support for multiple named plans needs a later convention.
- Future revision support will likely require stable IDs independent of mutable WBS positions and explicit dependency identities.
- Textual adds a runtime dependency and should be version-bounded and evaluated against the supported Python versions and terminal environments.
- The exact behavior when a work package is not connected by dependencies should remain simple: show an empty dependency state rather than treating isolation as invalid.

