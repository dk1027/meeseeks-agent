# WBS quality reference

## Core terms

- **Scope:** Boundaries of the result and the work required to produce it.
- **Work breakdown structure:** Hierarchical decomposition of total scope into deliverable-oriented components.
- **Work package:** Lowest managed WBS element; assignable, estimable, and verifiable as a unit.
- **Dependency:** Prerequisite relationship between work packages or gates.
- **Workstream:** Cohesive sequence of work packages that progresses with limited cross-stream synchronization.
- **Gate:** Decision or integration point whose completion permits dependent work.

## Decomposition tests

1. **Completeness:** Children cover all work needed for their parent outcome.
2. **Non-overlap:** Each child can have clear ownership without duplicating siblings.
3. **Outcome orientation:** Each child describes a result, not open-ended effort.
4. **Manageability:** Each leaf can be assigned and verified in a bounded delivery interval.
5. **Traceability:** Every acceptance criterion traces to a scoped deliverable.

Do not force equal depth across branches. Decompose only as far as needed for control and verification.

## Dependency meanings

- `hard`: successor cannot start meaningfully before its predecessor finishes.
- `interface`: streams can proceed after agreeing on a stable contract.
- `decision`: work waits on a scope- or implementation-changing choice.
- `environment`: work needs credentials, infrastructure, tooling, or external state.
- `preferred`: ordering reduces rework but is not mandatory.
- `integration`: independently completed outputs must be joined and tested.

## Warning signs

- The WBS is only a chronological to-do list.
- Branches are named for teams instead of deliverables.
- Work packages lack observable boundaries.
- Acceptance criteria merely repeat implementation steps.
- Parallel streams modify the same central files.
- One stream consumes another stream's unfinished concrete code.
- Integration and testing are only implied.
- Material scope remains hidden behind placeholders.
- Dependencies form a cycle or an integration gate lacks an owner.

## Sizing for weaker builder agents

Prefer a package with one outcome, a small related file set, explicit interfaces, named negative cases, preservation requirements, deterministic offline verification, and a clean handoff artifact. Split packages that require simultaneous architecture discovery and broad implementation.
