# Development Wing Records

This folder contains the **development wing** records of the BMAD methodology. While the
research wing answers the questions "what to do, why, how do we validate", the development
wing answers "how do we take this to production".

## Folder Structure

```
docs/development/
├── README.md                    (this file)
├── tech-debt.md                 (technical debt tracking)
│
├── _template_IR.md              (Implementation Readiness template)
├── _template_SP.md              (Sprint template)
├── _template_QR.md              (Quality Review template)
├── _template_PR.md              (Production Readiness template)
│
├── IR-001.md, IR-002.md, ...   (Implementation Readiness records)
├── SP-001.md, SP-002.md, ...   (Sprint records)
├── QR-001.md, QR-002.md, ...   (Quality Review records)
├── PR-001.md, PR-002.md, ...   (Production Readiness records)
│
├── stories/
│   ├── _template_S.md           (Story template)
│   └── S-001.md, S-002.md, ...  (Story records)
│
└── incidents/
    ├── _template_PM.md          (Post-Mortem template)
    └── PM-001.md, PM-002.md, ... (Post-Mortem records)
```

---

## Record Types and Usage

### 1. Implementation Readiness (IR-id)

**When:** Before moving research findings into development
**Purpose:** Guarantee all inputs are ready before starting development
**Gate:** Gate 1 (Readiness Check)

**Creating a new record:**
```bash
# Copy the template
cp _template_IR.md IR-001.md

# Fill in the content
# - List research inputs (E/R/D/C-ids)
# - Reference design documents
# - Define success criteria
# - Identify technical dependencies
# - Do risk assessment
```

**Checklist:** Detailed checklist inside the template

---

### 2. Sprint (SP-id)

**When:** At the start of each sprint
**Purpose:** Define the sprint scope clearly, measurably, and realistically
**Gate:** Gate 2 (Scope Approval)

**Creating a new record:**
```bash
cp _template_SP.md SP-001.md

# Fill in the content
# - Define the sprint goal (one sentence)
# - List stories (S-id + priority + points)
# - Check capacity (against velocity)
# - Time-box technical debt
# - Identify blockers and dependencies
```

**During the sprint:** Daily notes can be added (optional)
**At the end of the sprint:** Fill in the review and retrospective sections

---

### 3. Story (S-id)

**When:** During sprint planning
**Purpose:** Define a work unit ready for implementation with clear acceptance criteria
**Format:** User story (As a ... I want ... So that ...)

**Creating a new record:**
```bash
cd stories/
cp _template_S.md S-001.md

# Fill in the content
# - Write the user story sentence
# - Define acceptance criteria (Given/When/Then)
# - Split into technical tasks
# - Check the definition of done
```

**Story statuses:**
- `backlog` → `sprint` → `in-progress` → `review` → `done`
- If blocked: update the status, add to the blocker note

---

### 4. Quality Review (QR-id)

**When:** For every PR/MR, before merge
**Purpose:** Enforce code quality standards
**Gate:** Gate 3 (Quality Gate)

**Creating a new record:**
```bash
cp _template_QR.md QR-001.md

# Fill in the automatic checks section
# - Test coverage
# - Test results
# - Linter/formatter
# - Security scan
# - Performance regression

# Fill in the manual checks section
# - Code review feedback
# - Documentation status
# - Breaking changes
# - Technical debt
```

**Merge criteria:** All mechanical checks PASS + at least one code review APPROVED

---

### 5. Production Readiness (PR-id)

**When:** Before production deploy
**Purpose:** Guarantee operational readiness and rollback plan
**Gate:** Gate 4 (Production Readiness)

**Creating a new record:**
```bash
cp _template_PR.md PR-001.md

# Fill in the content
# - List the release scope (QR-ids)
# - Record staging test results
# - Detail the rollback plan
# - Verify monitoring and alerting
# - Make a feature flag plan
# - Prepare the runbook
# - Define the incident response plan
```

**After deploy:** Fill in the "Deploy Result" section (metrics, PM-id if incident)

---

### 6. Post-Mortem (PM-id)

**When:** After every SEV1/SEV2 production incident
**Purpose:** Learning and improvement (not blame)
**Required:** Mandatory for SEV1/SEV2, optional for SEV3

**Creating a new record:**
```bash
cd incidents/
cp _template_PM.md PM-001.md

# Fill in the content (within 24-48 hours)
# - Executive summary
# - Timeline (all times UTC)
# - Impact (user, business, technical)
# - Root cause (5 Whys)
# - Detection and response analysis
# - Lessons learned
# - Action items (owner, deadline, status)
```

**Blameless culture:** The purpose is not to find a guilty party, but to improve the system

---

### 7. Technical Debt (tech-debt.md)

**When:** Checked at every QR, added if debt exists
**Purpose:** Transparently track technical debt and make a repayment plan
**Format:** Table + categories + metrics

**Adding debt:**
1. Identified during QR
2. Add a new row to `tech-debt.md`
3. Add a TODO comment: `// TODO: [TD-XXX] description`
4. Determine priority (P0/P1/P2/P3)
5. Determine target sprint (mandatory for P0/P1)

**Paying off debt:**
1. Debt resolved
2. Move from "Active Debts" table to "Paid Debts" table
3. Record the solution details, sprint, QR-id
4. Delete the TODO comment

---

## Development Flow

### Flow 1: Research to Development

```
1. Research finding approved (E/R/D/C-id)
   ↓
2. Implementation Readiness (IR-id) — Gate 1
   ↓
3. Sprint Planning (SP-id) — Gate 2
   ↓
4. Implement stories (S-id)
   ↓
5. Quality Review (QR-id) — Gate 3
   ↓
6. Production Readiness (PR-id) — Gate 4
   ↓
7. Deploy → Monitoring → (PM-id if incident)
```

### Flow 2: Development Back to Research

```
1. Question arose during implementation
   ↓
2. Formulate the question (new research question)
   ↓
3. Choose the appropriate mode (A/B/C/D)
   ↓
4. Open a research record (E/R/D/C-id)
   ↓
5. Return to development after approval
```

---

## Record Chaining Examples

### Example 1: Feature Development
```
E-045 (BFS optimization approved)
  → IR-012 (implementation readiness: READY)
    → SP-003 (Sprint 3 planned)
      → S-027 (Story: BFS implementation)
        → QR-028 (code review: APPROVED)
          → PR-007 (production readiness: READY)
            → Deploy successful
```

### Example 2: Incident and Improvement
```
PR-007 (deployed)
  → PM-003 (incident: memory leak)
    → TD-042 (technical debt: memory profiling missing)
      → SP-004 (next sprint: debt repayment)
        → S-031 (Story: add memory profiling)
          → QR-032 (review: APPROVED)
            → TD-042 (debt paid)
```

### Example 3: Research → Development → Research Cycle
```
D-023 (design: new onboarding flow)
  → IR-015 (readiness: READY)
    → SP-005 (Sprint 5)
      → S-035 (Story: onboarding UI)
        → User testing: flow not understood
          → B-024 (qualitative research: user feedback)
            → D-025 (design revision)
              → IR-016 (new readiness)
                → Continue...
```

---

## Best Practices

### 1. Record Discipline
- Every decision/output is linked to a record
- No claims without records
- Follow templates, don't add custom fields

### 2. Honesty
- Don't distort test results
- Don't hide technical debt
- Report incidents
- Be open to rollback

### 3. Iteration
- Return to a previous stage when needed
- If a question arises during development, return to research
- Take sprint retrospectives seriously

### 4. Quality Standards
- Test coverage >= 80%
- Code review mandatory
- Security scan clean
- Documentation up to date

### 5. Transparency
- Technical debt visible
- Incident post-mortems shared
- Metrics tracked
- Blockers communicated immediately

---

## Related Documents

- [Development Methodology](../bmad/development-methodology.md) — Development wing manifesto
- [Research Methodology](../bmad/research-methodology.md) — Research wing manifesto
- [Project Context](../project-context.md) — Two-wing structure and integration
- [Usage Guide](../bmad/usage-guide.md) — How to use both wings

---

## Questions and Help

- Don't know which template to use? Look at the "When" sections above
- Template missing? Format details in [Development Methodology](../bmad/development-methodology.md) §3
- How does the Research ↔ Development transition work? The bridge mechanism is explained in [Development Methodology](../bmad/development-methodology.md) §4
- How is technical debt managed? Read the guide in the `tech-debt.md` file
