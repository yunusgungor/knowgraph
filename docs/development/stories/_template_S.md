# Story: S-XXX — [Story Title]

> This template is used for User Story (S) records.
> Stories are created during sprint planning and tracked throughout implementation.

## Story: S-XXX — [Story title]

- **Date:** [YYYY-MM-DD]
- **Status:** backlog | sprint | in-progress | review | done | blocked
- **Sprint:** [SP-id reference, e.g. SP-003]
- **Priority:** Critical / High / Medium / Low
- **Story points:** [X points]
- **Assignee:** [@username]
- **Epic:** [Epic-id or "standalone"]

---

## User Story

**As a** [user role]  
**I want** [what I want to be able to do]  
**So that** [my goal/value]

### Example
**As a** system administrator  
**I want** to be able to filter user activities  
**So that** I can quickly detect problematic behavior

---

## Acceptance Criteria

> For the story to count as "done", all criteria must be met

- [AC-001] **Given** [initial state] **When** [action] **Then** [expected result]
  - Experiment: E-XXX
  - Type: agent-verifiable | manual
  - Measured: true | false
  - Verify: [test command]
- [AC-002] **Given** [initial state] **When** [action] **Then** [expected result]
  - Experiment: E-XXX
  - Type: agent-verifiable | manual
  - Measured: true | false
  - Verify: [test command]
- [AC-003] **Given** [initial state] **When** [action] **Then** [expected result]
  - Experiment: E-XXX
  - Type: agent-verifiable | manual
  - Measured: true | false
  - Verify: [test command]

### Example
- [AC-001] **Given** I am on the admin panel **When** I select the "last 7 days" filter **Then** I only see the logs from the last 7 days
  - Experiment: E-001
  - Type: agent-verifiable
  - Measured: true
  - Verify: curl http://localhost:8000/api/logs?days=7
- [AC-002] **Given** the log list is loading **When** I change the filter **Then** I see a loading spinner
  - Experiment: E-001
  - Type: agent-verifiable
  - Measured: true
  - Verify: check_ui_spinner.py
- [AC-003] **Given** there are no logs **When** I load the page **Then** I see the "No logs found" message
  - Experiment: E-001
  - Type: agent-verifiable
  - Measured: true
  - Verify: check_empty_state.py

---

## Technical Tasks

> Technical steps required to complete the story

- [ ] Task 1: API endpoint implementation (AC: AC-001) — [@username]
- [ ] Task 2: Frontend component (AC: AC-002, AC-003) — [@username]
- [ ] Task 3: Database migration (AC: AC-001) — [@username]
- [ ] Task 4: Unit tests (AC: AC-001, AC-002, AC-003) — [@username]
- [ ] Task 5: Integration tests (AC: AC-001) — [@username]
- [ ] Task 6: Documentation — [@username]

---

## Definition of Done

> General criteria for the story to be truly finished

- [DoD-001] All acceptance criteria met (AC: AC-001, AC-002, AC-003)
  - Verify: pytest tests/
  - Evidence: test output
- [DoD-002] Code review done and approved
  - Verify: QR-001 record exists
  - Evidence: QR record
- [DoD-003] Unit test coverage >= 80%
  - Verify: coverage report
  - Evidence: coverage output
- [DoD-004] Integration test written and passed
  - Verify: pytest tests/integration/
  - Evidence: test output
- [DoD-005] Documentation updated
  - Verify: docs/ updated
  - Evidence: git diff
- [DoD-006] Tested on staging
  - Verify: manual test
  - Evidence: test results
- [DoD-007] Product owner accepted
  - Verify: PO sign-off
  - Evidence: approval message

---

## Dependencies

- **Depends on this story:** [Other S-ids — cannot start before this finishes]
- **This story depends on:** [Other S-ids — cannot start before these finish]
- **API dependency:** [Which APIs required, ready?]
- **Infrastructure dependency:** [Database, queue etc.]

---

## Design / UX

- **Mockup:** [Figma/Sketch link or file]
- **UX flow:** [User flow diagram]
- **Design review:** ✓ Done / ✗ Not needed / ⚠ Pending

---

## Notes / Tracking

### Blockers
- [YYYY-MM-DD]: [Blocker description] → Owner: [who] → Status: [open/resolved]

### Progress Updates
- [YYYY-MM-DD]: [Update note, e.g. "API completed, frontend started"]
- [YYYY-MM-DD]: [Update note]

### Decisions
- [YYYY-MM-DD]: [Technical/design decision taken and its rationale]

---

## Test Strategy

### Unit Tests
- [Which modules/functions will be tested]
- [Test coverage target: %X]

### Integration Tests
- [Which integration points will be tested]
- [API endpoint tests, database tests]

### Manual Tests
- [Manual test scenarios — for QA]

---

## Research Inputs

> Which research findings this story is based on

- [E-id / R-id / D-id / C-id references]
- Example: E-045 (performance optimization approval), D-012 (user flow design)

---

## Completion

- **Completion date:** [YYYY-MM-DD]
- **PR/MR:** [Pull request link]
- **QR record:** [QR-id reference]
- **Demo:** [Demo link/video or "done"]
- **Retrospective notes:** [Lessons learned from this story]
