# Meeseeks Agents

_Don't tell me it is done. Show me it is done_

Meeseeks is an independent software change verification agent that comes as a CLI and skills collection. Give it a task description and acceptance criteria, and it will review code, run checks, look for edge cases, and provide a final verdict backed by reproducible evidence.


1. Build code and write tests using your favorite methods. Run `meeseeks draft <your-task.toml>` or the `/meeseeks.draft_task_summary` skill to create a task TOML file that describes what you've built. You can also draft the task before you start building; Meeseeks will help you define the task and its acceptance criteria.

2. Call Meeseeks by running `meeseeks verify <your-task.toml>` or `/meeseeks.verify` to adversarially review the code. Meeseeks verifies completeness and correctness against the task TOML, starting from the assumption that the work may be incomplete or incorrect. It also scrutinizes the task specification to avoid garbage-in, garbage-out results.

3. Meeseeks declares the task `complete`, `incomplete`, or `inconclusive` and produces evidence to support the verdict.

4. Run `/meeseeks.tell_project_context` to tell Meeseeks how your project works—for example, how to build and test it.


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

Run `meeseeks draft .meeseeks/your-task.toml`, use the `/meeseeks.draft_task_summary` skill, or write the file by hand. The command and skill both guide you through the task description, observable acceptance criteria, exclusions, and useful verification commands, and produce the same task format.

## Meeseeks input and output

### Task TOML file

The task file is the verification contract. Acceptance criteria should describe observable outcomes rather than implementation steps.

```toml
version = 1
title = "Add rate limiting to the login endpoint"
description = """
Limit repeated failed login attempts from a single IP address without changing
the behavior of successful logins.
"""

[[acceptance_criteria]]
id = "AC-1"
description = "The sixth failed login attempt from one IP within ten minutes returns HTTP 429."

[[acceptance_criteria]]
id = "AC-2"
description = "A successful login resets the failure count for that IP."

[[acceptance_criteria]]
id = "AC-3"
description = "Failed attempts are allowed again after the ten-minute window expires."

out_of_scope = [
    "Sharing rate-limit state between application instances",
]

[verification]
commands = [
    "pytest tests/auth",
    "ruff check src tests",
]
```

Each acceptance criterion has a stable ID so the report can connect its verdict to specific evidence. Verification commands are useful project hints, not proof by themselves; Meeseeks may inspect code and perform additional checks.

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
