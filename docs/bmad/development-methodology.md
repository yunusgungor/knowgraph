# Development Methodology Manifesto

**Version:** 2.0.0
**Purpose:** Defines the core rules, process flow, and quality standards of the BMAD development methodology.

---

## §1 Development Flow

```
Sprint Planning → Story Creation → Implementation → Testing → Code Review → Done
```

Each stage depends on the output of the previous one.

---

## §2 Sprint Planning (Mode D)

### §2.1 Sprint Creation
- `sprint-status.yaml` is created with `bmad-sprint-planning`
- Sprint status: `backlog → in-progress → done`

### §2.2 Story Sequencing
- Stories are processed in epic order
- Each story can be completed independently
- The previous story's learnings are carried over to the next story

### §2.3 Sprint Status Format
```yaml
development_status:
  epic-1: backlog
  1-1-user-auth: ready-for-dev
  1-2-account: in-progress
  epic-1-retrospective: optional
```

---

## §3 Story Creation (Mode C)

### §3.1 Story Creation
- The story file is created with `bmad-create-story`
- Story metadata is required: Experiment, Type, Measured, Verify
- Task↔AC mapping is required
- DoD identifier is required

### §3.2 Story Format
```markdown
# Story X.Y: Title

Status: ready-for-dev
experiment_refs:
  - id: E-001
    scope: AC-001, AC-002
    status: APPROVED

## Acceptance Criteria

1. [AC-001] **Given** ... **When** ... **Then** ...
   - Experiment: E-001
   - Type: agent-verifiable
   - Measured: true
   - Verify: curl

## Technical Tasks

- [ ] Task 1: Description (AC: AC-001)
  - [ ] Subtask 1.1: Detail

## Definition of Done

- [ ] DoD-001: All ACs met (AC: AC-001)
  - Verify: curl
  - Evidence: test output

## Quality Record (QR)

| DoD Item | Status | Evidence | Date |
|----------|-------|-------|-------|
| DoD-001 | ⏳ pending | — | — |
```

### §3.3 Story Validation
- The guard hook validates the story metadata
- If metadata is missing, validation returns **DENY**
- Hypothesis ACs cannot be implemented

### §3.4 Experiment Approval Gate
- Prerequisite for proceeding to story implementation: all `experiment_refs[].status` fields must be **`APPROVED`**
- Stories without `APPROVED` status are not accepted by `bmad-dev-story` (Mode A)
- The guard hook verifies each experiment reference's status as `APPROVED`
- No code writing permission is granted without experiment approval

---

## §4 Implementation (Mode A)

### §4.1 Code Writing Rules
- Red-green-refactor loop
- Test first development
- Implementation on a per-AC basis
- **A documentary decision does NOT grant code writing permission**

### §4.1.1 Git Operations
- Changes must be committed at each implementation step
- Commit message format: `[Story X.Y] <change description>`
- When implementation is complete, all changes must be committed
- Without a commit, the Testing (§5) stage cannot be reached

### §4.2 Guard Hook Integration
- Code writing permission: requires an approved experiment record
- Story metadata validation
- Experiment reference check

### §4.3 Code Quality Standards
- Existing tests must pass
- New tests must be added
- Linting and static analysis
- Fixes after code review

---

## §5 Testing (Mode A)

### §5.1 Test Strategy
- **Unit tests:** Business logic, core functionality
- **Integration tests:** Component interactions
- **E2E tests:** User flows
- **Regression tests:** Existing functionality

### §5.2 AC Verification
- Each AC's Verify method is executed
- Results are saved to the story file
- Failed AC = implementation is stopped

### §5.3 Test Formats
```markdown
## Test Results

### Unit Tests
- X passed, Y failed

### Integration Tests
- X passed, Y failed

### AC Verification
| AC | Status | Method | Evidence |
|----|-------|--------|----------|
| AC-001 | ✅ verified | curl | response body |
| AC-002 | ❌ failed | test | error log |
```

---

## §6 Code Review (Mode A)

### §6.1 Review Process
- Adversarial review with `bmad-code-review`
- Parallel review layers:
  - **Blind Hunter:** General code quality
  - **Edge Case Hunter:** Edge case analysis
  - **Acceptance Auditor:** AC metadata + Task↔AC + DoD check

### §6.2 Review Outcome
- **Approve:** Story done — After Approve, §9 Session Closure steps are triggered
- **Changes Requested:** Fixed → Review again
- **Blocked:** Obstacles removed → Review again

### §6.3 Review Findings
```markdown
## Senior Developer Review (AI)

**Outcome:** Changes Requested
**Date:** 2026-08-20

### Action Items
- [ ] High: AC metadata missing (AC-003)
- [x] Medium: Task↔AC mapping fixed
- [ ] Low: DoD-002 Verify field empty
```

---

## §7 Quality Record (QR) (Mode A)

### §7.1 QR Creation
- A QR record is created when the story is completed
- Status, evidence and date for each DoD item
- Record chain: S → QR → PR

### §7.2 QR Format
```markdown
# Quality Record: QR-<sequence>

| Field | Value |
|------|-------|
| Story | <story_key> |
| Date | YYYY-MM-DD |
| QR Status | pass | fail | partial |

## DoD Verification Results

| DoD Item | Status | Evidence | Date |
|----------|-------|-------|-------|
| DoD-001 | ✅ passed | curl output | 2026-08-20 |
| DoD-002 | ❌ failed | test output | 2026-08-20 |
```

### §7.3 QR Approval
- All DoD items passed = QR approved
- Partial approval = missing items are listed
- Rejection = items that need to be fixed

---

## §8 Methodology Compliance

### §8.1 Guard Hook Compliance
- Code writing permission: requires experiment approval
- Story metadata validation
- Experiment reference check

### §8.2 Skill Compliance
| Skill | Mode | BRIDGE |
|-------|-----|-------|
| bmad-create-story | Mode C | #1 |
| bmad-dev-story | Mode A | #2 + #3 |
| bmad-code-review | Mode A | — |
| bmad-sprint-planning | Mode D | — |
| bmad-create-epics-and-stories | Mode C | — |

### §8.3 Record Chain Compliance
```
E (Experiment) → IR (Implementation Readiness) → SP (Sprint Planning) → S (Story) → QR (Quality Record) → PR (Production Readiness)
```

Each stage depends on the output of the previous one. Every link of the chain requires approval.

**Note:** During the implementation stage, a git commit is required after every step (§4.1.1). Without a commit, the Testing (§5) stage cannot be reached.

### §8.4 Critical Gates and Concepts

| Concept | Definition | Detail |
|--------|-------|-------|
| **APPROVED** | Experiment approval status | §3.4 - Story impl. prerequisite |
| **DENY** | Guard/stop hook blocking decision | Code writing or session closure is blocked |
| **Hypothesis** | AC awaiting experiment approval | `[HYPOTHESIS]` tag, cannot be implemented |
| **QR** | Quality Record | `docs/quality/QR-XXX.md`, required after done |
| **IR** | Implementation Readiness | `docs/development/IR-XXX.md`, Gate 1 |
| **PR** | Production Readiness | `docs/development/PR-XXX.md`, Gate 4 |

---

## §9 Session Closure

When a story is completed and the code review is approved, the session is closed. This process includes the following steps:
- A Quality Record (QR) is created and approved (§7)
- The story status is marked as "done" (§6.2)
- The sprint status is updated if necessary (§2.1)

Session closure is the final step of the development cycle and is required to move on to the next story.
