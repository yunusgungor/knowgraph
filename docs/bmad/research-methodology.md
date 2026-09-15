# Research Methodology Manifesto

**Version:** 2.0.0
**Purpose:** Defines the core rules, modular structure, and gate rules of the BMAD (Behavior-Driven Methodology for AI Development) research methodology.

---

## §1 Core Principles

### §1.1 Record Chain
The methodology chain proceeds in the following order:

```
Experiment (E) → Implementation Readiness (IR) → Sprint Planning (SP) → Story (S) → Quality Record (QR) → Production Readiness (PR)
```

Each stage depends on the output of the previous one. Every link of the chain requires approval.

> **Required record chain rules:** Sprint Planning cannot be started without IR; every approved transition is permanently recorded with a git commit; the Experiment Approval field is required in story, QR, and PR outputs.

### §1.2 Core Rule
> **A documentary decision is not code writing permission. Code is subject to Mode A mechanical approval in all cases.**

This rule applies to all modes. Documentary outputs such as PRD, architecture, and UX design do not grant code writing permission. Code writing always requires experiment approval.

### §1.3 Realization Rule
> **Realization comes with numerical validation: if a design transforms into a feature, it is bound to a Mode A measurement (D-id → E-id).**

When design decisions become features, they must be bound to an experiment measurement.

---

## §2 Mode System

### §2.1 Mode A — Code (Implementation)
- **Scope:** Code writing, testing, deploy
- **Gate:** Guard hook (PreToolUse) — requires an approved experiment record
- **Evidence Type:** Experiment record (E-XXX), test output, deployment log
- **Record Format:** `docs/experiments/E-XXX.md`, story file, QR record
- **Protection:** Guard hook blocks code writing (fail-closed)

### §2.2 Mode B — Framing, Exploration, Synthesis (Framing)
- **Scope:** Brainstorming, idea generation, concept development
- **Gate:** Documentary quality control
- **Evidence Type:** Brainstorm output, concept brief
- **Record Format:** Project files, docs/ directory
- **Protection:** None (fail-open)

### §2.3 Mode C — Needs, PRD, Requirements, UX, Architecture (Design)
- **Scope:** PRD, UX design, architecture decisions, requirements analysis
- **Gate:** Documentary quality control + implementation readiness check
- **Evidence Type:** PRD, architecture doc, UX spec, epics.md
- **Record Format:** `docs/planning/` directory
- **Protection:** None (fail-open) — but does not grant code writing permission

### §2.4 Mode D — Sprint Management, Documentation (Management)
- **Scope:** Sprint planning, retrospective, documentation
- **Gate:** Documentary quality control
- **Evidence Type:** Sprint status, retrospective notes, documentation
- **Record Format:** `sprint-status.yaml`, docs/ directory
- **Protection:** None (fail-open)

---

## §3 Gate Rules

Each mode's gate rules determine the quality and compliance of that mode's output.

### §3.1 Mode A Gate Rules
1. **Experiment Approval:** A VERIFIED experiment approval matching the scope is required before writing code
2. **Guard Hook:** The PreToolUse hook blocks code writing (fail-closed)
3. **Stop Hook:** Blocks session closure if there are incomplete stories
4. **Story Metadata:** AC metadata completeness check (Experiment, Type, Measured, Verify)
5. **Task↔AC:** Every task must be bound to an AC
6. **DoD:** Every DoD item's identifier and verify fields are required

### §3.2 Mode B Gate Rules
1. **Documentary Output:** Every work session must produce an output
2. **Evidence Format:** Outputs must be clear and verifiable
3. **Record:** Outputs must be saved to the docs/ directory

### §3.3 Mode C Gate Rules
1. **Documentary Completeness:** PRD, architecture, and UX spec must be complete
2. **Requirement Mapping:** Every requirement must be linked to a story
3. **Code Writing Permission:** A documentary decision does NOT grant code writing permission
4. **Mode A Link:** Feature conversion is bound to a Mode A measurement (D-id → E-id)

### §3.4 Mode D Gate Rules
1. **Sprint Status:** sprint-status.yaml must be updated
2. **Story Status:** Stories must be ordered correctly
3. **Retrospective:** Action items must be recorded

---

## §4 Experiment Rules

### §4.1 Experiment Creation
- Every experiment must be recorded in the `docs/experiments/E-XXX.md` file
- The experiment record must contain the following fields (these labels are required — the gate parses them):
  - **Theory:** Which theory/framework it comes from
  - **Hypothesis:** H-NNN: the assumption being tested in "metric >= threshold" format
  - **Measurement Metrics:** Metric name + threshold value
  - **Experiment Design:** Inputs, procedure, control variables
  - **Code Scope:** File globs opened by the approval
  - **Status:** planned → APPROVED | REJECTED (written by the gate)

### §4.2 Experiment Approval
- Experiment approval is verified with `run_experiment.py --verify`
- Approved experiment: `status: APPROVED` and a valid HMAC signature
- Unapproved experiment: Code writing is blocked (guard hook)

### §4.3 Hypothesis Protection
- ACs without experiment approval are marked as `[HYPOTHESIS]`
- Hypothesis ACs cannot be implemented
- The user is shown the message "Experiment approval is required for this AC"

---

## §5 Story Rules

### §5.1 Story Creation
- Every story must be bound to an experiment record
- The story file must be located at `{implementation_artifacts}/<story-key>.md`
- Story metadata is required: Experiment, Type, Measured, Verify
- The `Experiment Approval` field is required in every story record: E-id, status, verification method, timestamp, git commit ref.

### §5.2 Story → Methodology Record
- When a story is created, the `docs/development/stories/S-<sequence>.md` record file is also created
- Methodology record: Date, Status, Story Title, Epic, AC, Experiment Refs, File List

### §5.3 Story Status Flow
```
backlog → ready-for-dev → in-progress → review → done
```

### §5.4 Story Metadata Requirements
For each AC:
- `[AC-XXX]` identifier
- `Experiment:` field (E-XXX or —)
- `Type:` field (agent-verifiable | user-evaluable | hybrid)
- `Measured:` field (true | false)
- `Verify:` field (verification method)

For each Task:
- `(AC: AC-XXX)` reference

For each DoD:
- `[DoD-XXX]` identifier
- `Verify:` field

---

## §6 Quality Record (QR) Rules

### §6.1 QR Creation
- **QR** is required: when the story is completed, `docs/quality/QR-<sequence>.md` is created; without QR approval the story cannot be accepted as `done`
- QR: contains status, evidence, and date for each DoD item
- QR updates the Quality Record section in the story file

### §6.2 QR Approval
- QR approval: All DoD items must be passed
- Partial approval: `status: partial` — missing items are listed
- Rejection: `status: fail` — items that need fixing are listed

---

## §7 Production Readiness (PR) Rules

### §7.1 PR Creation
- After QR approval, deploy preparation is performed
- The PR record is created at `docs/development/PR-XXX.md`
- **PR Status:** READY | WAITING

### §7.2 PR Cycle
- WAITING → Preparations completed → READY
- READY → Deploy is performed → Story transitions to `done` status

---

## §8 Guard Hook Rules

### §8.1 Code Writing Block (DENY)
- When there is no code writing permission, the guard hook result is **DENY**: unapproved experiment, missing story metadata, or a Hypothesis AC
- Code cannot be written to files with an unapproved experiment record
- Files with missing story metadata are blocked

### §8.2 Story Metadata Validation
- AC metadata completeness check
- Task↔AC mapping check
- DoD structural check

### §8.3 Stop Hook
- If there are incomplete stories, session closure is blocked
- If there are unapproved code changes, session closure is blocked

### §8.4 Audit Hook
- Tool usage is logged
- Methodology compliance is checked (at warning level)

---

## §9 Module Map

| Mode | Scope | Gate | Protection | Evidence Type |
|-----|--------|------|--------|------------|
| Mode A | Code | Guard hook | fail-closed | E-XXX, test, deploy |
| Mode B | Framing | Documentary quality | fail-open | Brainstorm, concept |
| Mode C | PRD/UX/Architecture | Documentary completeness | fail-open | PRD, arch, UX spec |
| Mode D | Sprint/Documentation | Documentary quality | fail-open | Sprint status, retro |

---

## §10 Compliance

This methodology is compliant with the following components:

| Component | Status | Mode |
|---------|-------|-----|
| guard hook | ✅ Active | Mode A |
| audit hook | ✅ Active | All modes |
| stop hook | ✅ Active | Mode A |
| bmad-agent-dev | ✅ Mode A | Code |
| bmad-create-story | ✅ Mode C | Story creation |
| bmad-dev-story | ✅ Mode A | Story realization |
| bmad-code-review | ✅ Mode A | Change review |
| bmad-sprint-planning | ✅ Mode D | Sprint management |
| bmad-create-epics-and-stories | ✅ Mode C | Epic/story decomposition |
| bridge doc | ✅ v3.0 | Bridge document |

---

## §11 Required Control and Record Rules

### §11.1 Required Terms
- **approved experiment**: only an experiment with `status: APPROVED` and a valid HMAC signature; otherwise code writing is **DENY**d.
- **Hypothesis**: an AC awaiting experiment approval. Marked with the `[HYPOTHESIS]` tag, cannot be implemented.
- **DENY**: the guard/stop hook's blocking decision. Code writing or session closure is blocked.
- **QR (Quality Record)**: `docs/quality/QR-<sequence>.md` — required when the story is completed. Without QR approval, `done` is not accepted.
- **IR (Implementation Readiness)**: `docs/development/IR-<sequence>.md` — Gate 1. Required before Sprint Planning.
- **PR (Production Readiness)**: `docs/development/PR-<sequence>.md` — Gate 4. Required before deploy.

### §11.2 Required Record Paths
| Record | Path | Valid Status Values |
|-------|-----|------------------------|
| Experiment (E) | `docs/experiments/E-XXX.md` | planned → APPROVED \| REJECTED |
| IR | `docs/development/IR-XXX.md` | READY \| INCOMPLETE |
| SP | `docs/development/SP-XXX.md` | planned \| in-progress \| completed \| cancelled |
| Story (S) | `docs/development/stories/S-XXX.md` | backlog \| sprint \| in-progress \| review \| done \| blocked |
| QR | `docs/quality/QR-XXX.md` | pass \| fail \| partial |
| PR | `docs/development/PR-XXX.md` | READY \| WAITING |
