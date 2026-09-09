# Dev Skill → Methodology Bridge

**Version:** 4.0.0
**Purpose:** Connect BMAD native story workflows to the research methodology's experiment-gated development model.

---

## §1 General Context

This document defines how the `bmad-create-story` and `bmad-dev-story` skills integrate with the research methodology. Methodology chain:

```
Epic/Story → Experiment Record (E) → Story Implementation (S) → Quality Record (QR)
```

Every story must be linked to one or more approved experiment records. Stories without a link are marked as "hypothesis" — code writing requires experiment approval.

---

## §2 Acceptance Criteria Dynamic Processing Rules

### §2.1 AC ↔ Experiment Link

Each Acceptance Criterion must be associated with an experiment record:

```yaml
# In Story YAML frontmatter
experiment_refs:
  - id: E-001
    scope: "AC #1 and #2 — user authentication flow"
    status: APPROVED  # APPROVED | PENDING | REJECTED
  - id: E-002
    scope: "AC #3 — password reset"
    status: PENDING   # This AC has not yet received experiment approval
```

**Rule:** ACs with `status: PENDING` or `status: REJECTED` cannot be implemented. In the story file, these ACs are marked as `[HYPOTHESIS]`.

### §2.2 AC Metadata Slots

In the story template, the following metadata fields are required for each AC:

```markdown
## Acceptance Criteria

1. [AC-001] **Given** ... **When** ... **Then** ...
   - Experiment: E-001
   - Type: agent-verifiable | user-evaluable | hybrid
   - Measured: true | false
   - Verify: curl | puppeteer | lighthouse | test | manual

2. [AC-002] **Given** ... **When** ... **Then** ... [HYPOTHESIS]
   - Experiment: — (awaiting experiment approval)
   - Type: agent-verifiable
   - Measured: false
   - Verify: test
```

### §2.2a Technical Tasks ↔ AC Mapping

Every Technical Task must be bound to an AC:

```markdown
## Technical Tasks

- [ ] Task 1: Create API endpoint (AC: AC-001)
  - [ ] Subtask 1.1: Define route
  - [ ] Subtask 1.2: Write handler
- [ ] Task 2: Add validation (AC: AC-001, AC-002)
  - [ ] Subtask 2.1: Input validation
```

**Rule:** A task without an AC reference = validation warning. The guard hook validates this mapping.

### §2.2b Definition of Done ↔ AC Mapping

Each DoD item must be bound to an AC and have a defined verification method:

```markdown
## Definition of Done

- [ ] DoD-001: All ACs satisfied (AC: AC-001, AC-002)
  - Verify: curl + puppeteer
  - Evidence: test output
- [ ] DoD-002: Tests passed (AC: AC-001)
  - Verify: pytest
  - Evidence: test output
```

### §2.3 Methodology Record Creation (BRIDGE #1)

When `bmad-create-story` completes:

1. The native story file (`{implementation_artifacts}/<story-key>.md`) is generated
2. The `docs/development/stories/S-<sequence>.md` methodology record is created
3. Fields in the methodology record:

```markdown
# Methodology Record: S-<sequence>

| Field | Value |
|------|-------|
| Date | YYYY-MM-DD |
| Status | backlog \| sprint \| in-progress \| review \| done \| blocked |
| Story Title | <story title> |
| Epic | <epic num> |
| Acceptance Criteria | <AC list — in et-tooling format> |
| Experiment Refs | <E-XXX list> |
| File List | <empty — filled after implementation> |
| Sprint Ref | <sprint-status.yaml reference> |
| Native Story | <story file path> |
```

4. A reference is added to the native story file:
   ```
   <!-- Methodology record: docs/development/stories/S-<sequence>.md -->
   ```

### §2.4 Post-Implementation Update (BRIDGE #2)

When `bmad-dev-story` completes:

1. The methodology record's Status field is updated from `in-progress` → `review`
2. The Dev Agent Record sections are filled in:
   - **Debug Log**: Applied fixes and issues encountered
   - **Completion Notes**: Brief summary
   - **File List**: Changed files (relative to project root)
   - **Change Log**: Change summary
3. Experiment results are added to the Experiment Refs field (if any)
4. The relevant section in the native story file is also updated

### §2.5 Quality Record (QR) Creation (BRIDGE #3)

When all DoD items are verified in `bmad-dev-story` Step 9, the QR record is created:

1. The `docs/quality/QR-<sequence>.md` file is created
2. QR content:

```markdown
# Quality Record: QR-<sequence>

| Field | Value |
|------|-------|
| Story | <story_key> |
| Story File | <story file path> |
| Date | YYYY-MM-DD |
| QR Status | pass | fail | partial |

## DoD Verification Results

| DoD Item | Status | Evidence | Date |
|----------|-------|-------|-------|
| DoD-001 | ✅ passed | curl output | 2026-08-20 |
| DoD-002 | ✅ passed | pytest output | 2026-08-20 |
| DoD-003 | ❌ failed | test output | 2026-08-20 |

## AC Verification Results

| AC | Status | Method | Evidence |
|----|-------|--------|----------|
| AC-001 | ✅ verified | curl | response body |
| AC-002 | ⏳ pending | — | — |

## Test Summary

- Unit tests: X passed, Y failed
- Integration tests: X passed, Y failed
- Regression: pass/fail

## File List

- file1.ts (new)
- file2.ts (modified)

## Change Summary

<change log summary>
```

3. The Quality Record section in the story file is updated:
   - Each DoD item is marked as ✅ or ❌
   - The QR Record Path field is filled in
4. The record chain is completed: S → QR → PR

### §2.5a Implementation Readiness (IR) Record Creation

When `bmad-check-implementation-readiness` completes, the IR record is created:

1. The `docs/development/IR-<sequence>.md` file is created
2. Copy the template from `templates/_template_IR.md` and fill the fields from the
   native readiness report with English labels:
   - **Date**, **Status**: `preparing` | `READY` | `INCOMPLETE`
   - **Research inputs**, **Design documents**, **Success criteria**
   - **Technical dependencies**, **Risk assessment**, **Gaps**
   - **Decision**: `READY` | `INCOMPLETE` + rationale
   - **Next step**: `proceed to sprint planning` | `return to research`
3. Add the reference `Methodology record: docs/development/IR-<sequence>.md` to the
   native report. The Decision field must be READY or INCOMPLETE and the Date field
   must be present (`scripts/check-methodology.sh §6` checks this).
4. The record chain is established: E → IR → SP.

### §2.5b Sprint Planning (SP) Record Creation

When `bmad-sprint-planning` completes, the SP record is created:

1. The `docs/development/SP-<sequence>.md` file is created
2. Copy the template from `templates/_template_SP.md` and fill the fields from the
   native sprint output with English labels:
   - **Date**, **Status**: `planned` | `in progress` | `completed` | `cancelled`
   - **Sprint goal**: one sentence
   - **Stories**: S-id list + priority + story points
   - **Capacity**: estimated points / team velocity
   - **Blockers**: known blockers + resolution plan
   - **Dependencies**, **Technical debt**
3. The Status field must be from the allowed values and the Date field must be
   present (`scripts/check-methodology.sh §6` checks this).
4. The record chain is established: IR → SP → S.

### §2.6 Production Readiness (PR) Record Creation (BRIDGE #4)

Before a production deploy, the deploy guard (Gate 4) requires a Production Readiness
record at `docs/development/PR-<sequence>.md`. This bridge step produces it from the
deployment surface (dev-story, quick-dev, agent-dev):

1. The `docs/development/PR-<sequence>.md` file is created
2. Copy the template from `docs/development/_template_PR.md` and fill the fields with
   English labels:
   - **Date**, **Status**: `preparing` | `READY` | `PENDING`
   - **Release type**: Major | Minor | Patch | Hotfix
   - **Version**, **Release scope** (QR-id list)
   - **Staging Test**, **Rollback Plan**, **Monitoring and Alerting**
   - **Feature Flags**, **Runbook**, **Incident Response**
   - **Decision**: `READY` | `PENDING` + rationale
   - **Next step**: `production deploy` | `complete the gaps`
3. The Decision field must be one of the allowed values and the Date field must be
   present (`scripts/check-methodology.sh §6` checks this).
4. The record chain is completed: QR → PR, satisfying the deploy guard's Gate 4
   enforcement.

---

## §3 Guard Hook Integration

### §3.1 Story-Experiment Mapping Check

When granting code writing permission, the guard hook does not only look at `docs/experiments/` records — it also verifies the experiment link of the ACs in the story file:

1. **If the target file is a story file** (`{implementation_artifacts}/*-*.md`):
   - Reads the `experiment_refs` field in the YAML frontmatter
   - Verifies that each reference exists under `docs/experiments/` and is `APPROVED`
   - If any reference is missing or unapproved, DENY

2. **If the target file is a code file**:
   - Existing behavior is preserved: a `docs/experiments/` record is searched
   - Additionally: the experiment link of the ACs of the story that the modified file belongs to is checked (optional, not a hard gate)

### §3.2 AC Metadata Validation

When the story file is written, the guard hook validates the AC metadata:

- Does every AC have an `[AC-XXX]` identifier?
- Is the `Experiment:` field filled in for every AC?
- Is the `Type:` field defined for every AC?
- Does every AC have a `Measured:` field?
- Does every AC have a `Verify:` field?
- Do ACs with Experiment=— have the `[HYPOTHESIS]` tag?

Missing metadata = DENY.

### §3.3 Task↔AC Mapping Check

The guard hook validates the Technical Tasks section:

- Does every task have an `AC: AC-XXX` reference?
- Is the referenced AC defined in the story?

Missing reference = DENY.

### §3.4 DoD Structural Check

The guard hook validates the Definition of Done section:

- Does every DoD item have a `[DoD-XXX]` identifier?
- Does every DoD item have a `Verify:` field?

Missing identifier = DENY.

### §3.5 Hypothesis Protection

ACs marked as `[HYPOTHESIS]`:
- Cannot be implemented (the guard hook returns DENY)
- The story status is updated to `blocked`
- The user is shown the message "Experiment approval is required for this AC"

### §3.6 Methodology Chain Validation (NEW)

When the story file is written, the guard hook validates the methodology chain:

- **Status = done**: The QR record (docs/quality/QR-XXX.md) must exist
- **Status = review/done**: The methodology record (docs/development/stories/S-XXX.md) must exist
- Missing record = DENY + "Run: python3 scripts/create-qr-record.py" or "python3 scripts/create-methodology-record.py" message

### §3.7 Programmatic Enforcement Summary

| Check | Enforcement Type | Error State |
|---------|-------------|-------------|
| Experiment approval | Hard gate (DENY) | Code cannot be written |
| Experiment refs | Hard gate (DENY) | Story cannot be written |
| AC metadata | Hard gate (DENY) | Story cannot be written |
| Task↔AC | Hard gate (DENY) | Story cannot be written |
| DoD identifier | Hard gate (DENY) | Story cannot be written |
| Methodology chain | Hard gate (DENY) | Story cannot be written |
| Methodology compliance | Soft (warning) | Written to the audit log |

### §3.8 Git Commit Discipline

Files generated or updated after BRIDGE #1, #2, or #3 **must be committed**:

| When | Commit Convention |
|----|---------------------|
| BRIDGE #1 (S record) | `[Story X.Y] methodology record created` |
| BRIDGE #2 (S update) | `[Story X.Y] dev agent record updated` |
| BRIDGE #3 (QR creation) | `[Story X.Y] quality record created` |

---

## §4 File Structure

```
docs/
├── bmad/
│   ├── dev-skill-to-methodology-bridge.md  ← This document (v4.0)
│   ├── research-methodology.md              ← Methodology manifesto
│   └── development-methodology.md           ← Development methodology
├── development/
│   ├── _template_S.md                       ← Methodology record template
│   └── stories/
│       ├── S-001.md                         ← Story methodology records
│       └── S-002.md
├── experiments/
│   ├── E-001.md                             ← Experiment records
│   └── E-002.md
└── quality/
    └── QR-001.md                            ← Quality Record entries

scripts/
├── check-methodology.sh                     ← Methodology chain validation
├── create-methodology-record.py             ← BRIDGE #1: create S-XXX.md
├── create-qr-record.py                      ← BRIDGE #3: create QR-XXX.md
└── run_experiment.py                        ← Experiment approval system
```

---

## §5 Checklist

What to check at each step of the story lifecycle:

- [ ] **Create Story**: Is the `Experiment` field filled in for each AC?
- [ ] **Create Story**: Do the ACs have `Type`, `Measured`, `Verify` fields?
- [ ] **Create Story**: Is `experiment_refs` defined in the frontmatter?
- [ ] **Create Story**: Does every task have an `AC: AC-XXX` reference?
- [ ] **Create Story**: Does every DoD item have `[DoD-XXX]` and `Verify:`?
- [ ] **Create Story**: Was the methodology record (S-XXX) created?
- [ ] **Dev Story**: Was experiment approval verified before implementation?
- [ ] **Dev Story**: Were ACs marked as hypothesis skipped?
- [ ] **Dev Story**: Was each AC's `Verify` method executed?
- [ ] **Dev Story**: Was evidence collected for each DoD item?
- [ ] **Dev Story**: Was the QR record (QR-XXX) created?
- [ ] **Dev Story**: Was the methodology record updated after completion?
- [ ] **Code Review**: Was the match between ACs and experiment results verified?
- [ ] **Code Review**: Was the AC metadata (Experiment, Type, Measured) verified?
- [ ] **Code Review**: Was the Task↔AC mapping verified?
- [ ] **Code Review**: Are the DoD items' evidence complete?
- [ ] **Dev Story**: Were the BRIDGE #1–3 files committed with separate commits?

---

## §6 Compliance

This document is compliant with the following skills:

| Skill | Compatibility | Note |
|-------|-----------|-----|
| bmad-create-story | ✅ BRIDGE #1 | Methodology record during story creation |
| bmad-dev-story | ✅ BRIDGE #2 + #3 | Post-implementation update + QR creation |
| bmad-create-epics-and-stories | ⚠️ Partial | AC format compatible but no experiment binding |
| bmad-code-review | ✅ | Acceptance Auditor AC metadata + Task↔AC + DoD check |
| guard hook | ✅ | Experiment + AC metadata + Task↔AC + DoD validation |
| stop hook | ✅ | Story status check (in-progress = block) |
| audit hook | ✅ | Methodology compliance warnings |
| bmad-edit-prd | ❌ REMOVED | DEPRECATED — merged into bmad-prd |
| bmad-testarch-atdd | ❌ Unlinked | Separate test workflow, not linked to ACs |

---

## §7 Session Closure

A session should be closed when the following steps are completed:

### §7.1 Closure Checklist
- [ ] Was the Verify method executed for all ACs?
- [ ] Was evidence collected for each DoD item?
- [ ] Was the QR record (QR-XXX) created?
- [ ] Was the methodology record (S-XXX) updated?
- [ ] Were the BRIDGE #1–3 files committed?
- [ ] Was the story status marked as `done`?

### §7.2 After Closure
- The story transitions to `done` status
- It becomes ready to move on to the next story
- The sprint status is updated if necessary
