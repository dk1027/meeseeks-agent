# Meeseeks Agents

_Don't tell me it is done. Show me it is done_

Meeseeks is an independent software change verification agent that comes as a CLI and skills collection. Give it a task description and acceptance criteria, and it will review code, run checks, look for edge cases, and provide a final verdict backed by reproducible evidence.


1. Define the work. Run `meeseeks draft <your-task.toml>` to create one verification contract, or invoke the `meeseeks-wbsify` skill to decompose broader scope into a work breakdown structure, parallel workstreams, a dependency map, and task TOML files.

2. Build code and tests using your preferred tools. Each task TOML represents one independently verifiable work package.

3. Run `meeseeks verify <your-task.toml>` to adversarially review the work. Meeseeks verifies completeness and correctness against the task contract, starting from the assumption that the work may be incomplete or incorrect. It also scrutinizes the contract to avoid garbage-in, garbage-out results.

4. Meeseeks declares the work package `complete`, `incomplete`, or `inconclusive` and produces evidence to support the verdict.


Meeseeks looks for `AGENTS.md` and `CLAUDE.md` from the current directory. You can specify additional instruction files in `.meeseeks/config.toml`:

```
agents_md = [
    "some/path/AGENTS.md",
    "some/other/path/CLAUDE.md"
]
```

## Setup

Run `meeseeks init` at your repository root to create a `.meeseeks` directory.

## How to use Meeseeks to verify work

Run `meeseeks draft .meeseeks/tasks/your-task.toml` or write the file by hand. For broader scope, invoke the `meeseeks-wbsify` skill. It creates `.meeseeks/plan.toml` plus one task contract per leaf work package under `.meeseeks/tasks/`.

The `meeseeks-` prefix provides a consistent namespace while keeping the skill portable across hosts:

```text
Codex:       $meeseeks-wbsify
Claude Code: /meeseeks-wbsify
```

## Meeseeks input and output

### Task TOML file

The task file is the verification contract for one work package. Its stable `id` connects it to the WBS and dependency graph. Acceptance criteria describe observable outcomes rather than implementation steps.

```toml
version = 1
id = "WP-1.2.3"
title = "Add rate limiting to the login endpoint"
description = """
Limit repeated failed login attempts from a single IP address without changing
the behavior of successful logins.
"""

out_of_scope = [
    "Sharing rate-limit state between application instances",
]

[[acceptance_criteria]]
id = "AC-1"
description = "The sixth failed login attempt from one IP within ten minutes returns HTTP 429."

[[acceptance_criteria]]
id = "AC-2"
description = "A successful login resets the failure count for that IP."

[[acceptance_criteria]]
id = "AC-3"
description = "Failed attempts are allowed again after the ten-minute window expires."

[verification]
commands = [
    "pytest tests/auth",
    "ruff check src tests",
]
```

The work-package ID must be unique within its plan. Each acceptance criterion has a stable ID within the work package so the report can connect its verdict to specific evidence. Verification commands are useful project hints, not proof by themselves; Meeseeks may inspect code and perform additional checks.

### Work-plan TOML file

The plan is an orchestration artifact, not a verification contract. It records the WBS, task files, workstream ownership, dependencies, and integration gates without duplicating acceptance criteria.

```toml
version = 1
title = "Meeseeks MVP"

[[workstreams]]
id = "authoring"
title = "Task authoring"
ownership = [
    "src/meeseeks/task.py",
    "src/meeseeks/commands/draft.py",
    "skills/draft-task/**",
]

[[workstreams]]
id = "verification"
title = "Verification infrastructure"
ownership = [
    "src/meeseeks/runs.py",
    "src/meeseeks/context.py",
    "src/meeseeks/report.py",
]

[[workstreams]]
id = "integration"
title = "Integrated verifier"
ownership = [
    "src/meeseeks/cli.py",
    "src/meeseeks/commands/verify.py",
]

[[work_packages]]
id = "WP-1.1.1"
wbs = "1.1.1"
task = "tasks/01-task-contract.toml"
workstream = "authoring"

[[work_packages]]
id = "WP-1.2.1"
wbs = "1.2.1"
task = "tasks/05-run-storage-and-commands.toml"
workstream = "verification"

[[work_packages]]
id = "WP-1.3.1"
wbs = "1.3.1"
task = "tasks/08-verification-backend.toml"
workstream = "integration"

[[dependencies]]
predecessor = "WP-1.1.1"
successor = "WP-1.3.1"
type = "integration"
reason = "The integrated verifier consumes the canonical task contract."

[[dependencies]]
predecessor = "WP-1.2.1"
successor = "WP-1.3.1"
type = "integration"
reason = "The integrated verifier consumes immutable run storage and command evidence."
```

Version 1 dependency types are `hard`, `interface`, `decision`, `environment`, `preferred`, and `integration`. Work packages referenced by dependencies must exist in the same plan. Ownership entries document coordination boundaries; they are not filesystem permissions.

For the MVP, `meeseeks verify` consumes individual task files. The plan is produced by `meeseeks-wbsify` for people and builder agents; plan-level orchestration is a later capability.

Run `meeseeks plan` to open a read-only explorer over an execution package: a collapsible workstream/work-package tree with a detail pane for the selected item. With no argument it looks for `.meeseeks/plan.toml` in the current directory; pass a path (`meeseeks plan path/to/plan.toml`) to open a plan elsewhere. The plan and every task file it references are validated before the explorer opens; a missing, malformed, unsupported, or inconsistent execution package fails with an actionable message and a nonzero exit instead of launching.

### Output

Meeseeks creates a directory under `.meeseeks/runs` using the task name and a timestamp. Existing verification runs are never overwritten.

For example, verifying `.meeseeks/login-rate-limit.toml` might create:

```text
.meeseeks/runs/login-rate-limit-20260725T184200Z/
├── verification_report.md
└── artifacts/
    ├── pytest-tests-auth.log
    └── ruff-check.log
```

#### verification_report.md

```markdown
# Verification report: Add rate limiting to the login endpoint

## Verdict

**incomplete** — AC-2 is not satisfied.

## Acceptance criteria

### AC-1 — Met

The limiter returns HTTP 429 on the sixth failed attempt. This is implemented in
`src/auth/rate_limit.py` and reproduced by `test_sixth_attempt_is_rejected`.

Evidence: [pytest-tests-auth.log](artifacts/pytest-tests-auth.log)

### AC-2 — Not met

The failure count is not cleared after a successful login. A focused verification
run reproduces the issue.

Evidence: [pytest-tests-auth.log](artifacts/pytest-tests-auth.log)

### AC-3 — Met

The implementation compares attempts against the configured ten-minute window,
and the expiry behavior is covered by `test_attempts_allowed_after_window`.

Evidence: [pytest-tests-auth.log](artifacts/pytest-tests-auth.log)

## Gaps

- Clear the IP's accumulated failures after a successful login.
- Add a regression test covering a successful login between failed attempts.
```

The verdict is one of:

- `complete`: every acceptance criterion is supported by sufficient evidence.
- `incomplete`: at least one acceptance criterion is not met.
- `inconclusive`: Meeseeks cannot make a defensible determination—for example, because the task is ambiguous or the verification environment is broken.

#### Zero or more artifact files

Artifacts may include command logs, test output, screenshots, or other files needed to reproduce the evidence in the report.
