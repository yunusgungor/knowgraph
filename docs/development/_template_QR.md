# Quality Review: QR-XXX — [Story/PR Reference]

> This template is used for Quality Review (QR) records.
> Represents Development Gate 3: enforces quality standards before code is merged.

## Quality Review: QR-XXX — [Story/PR reference]

- **Date:** [YYYY-MM-DD]
- **Status:** in-review | APPROVED | REJECTED | REVISED
- **Story:** [S-id reference, e.g. S-001]
- **PR/MR:** [Pull request link or ID]
- **Branch:** [feature/branch-name]
- **Changed files:** [How many files, how many +/− lines]

---

## Mechanical Checks (Automatic)

### Test Coverage
- **Rate:** [X%]
- **Threshold:** 80% (minimum)
- **Status:** ✓ PASS / ✗ FAIL
- **Notes:** [If coverage is low, which modules are missing]

### Test Results
- **Unit tests:** [X passed / Y total] → ✓ PASS / ✗ FAIL
- **Integration tests:** [X passed / Y total] → ✓ PASS / ✗ FAIL
- **E2E tests:** [X passed / Y total] → ✓ PASS / ✗ FAIL
- **Flaky tests:** [If any, which and why flaky]
- **Status:** ✓ ALL PASS / ✗ FAILURES

### Linter / Formatter
- **Linter:** ✓ PASS / ✗ FAIL
  - [Linter errors/warnings if any]
- **Formatter:** ✓ PASS / ✗ FAIL
  - [Format errors]
- **Status:** ✓ PASS / ✗ FAIL

### Security Scan
- **Vulnerability scan:** ✓ CLEAN / ✗ FOUND
  - [Findings if any: severity, CVE ID, package]
- **Dependency check:** ✓ PASS / ✗ FAIL
  - [Any dependency with known vulnerability]
- **Secret scanning:** ✓ CLEAN / ✗ FOUND
  - [Hardcoded secret, API key, password found?]
- **Status:** ✓ CLEAN / ✗ ISSUES FOUND

### Performance Regression
- **Benchmarks:** [Performance of critical functions]
  - [Function 1]: [X ms] (previous: [Y ms]) → [% change]
  - [Function 2]: [X ms] (previous: [Y ms]) → [% change]
- **Memory usage:** [X MB] (previous: [Y MB]) → [% change]
- **Status:** ✓ NO REGRESSION / ✗ REGRESSION DETECTED

### Skill Eval (bmad-eval-runner feed)
- **Skill:** [evaluated skill name]
- **Cases:** [X passed / Y total]
- **Run folder:** [run dir path]
- **Status:** ✓ ALL PASS / ✗ FAILURES / — (no eval ran)

---

## AC Verification Results

> One row per acceptance criterion of the reviewed story (S-XXX). AC
> identifiers and their `Verify:` methods must match the story's Acceptance
> Criteria section. Standard format: `| AC | Status | Method | Evidence |`.

| AC | Status | Method | Evidence |
|----|--------|--------|----------|
| AC-XXX | ✅ verified / ⏳ pending / ❌ failed | [method: e.g. guard unit test, curl, pytest] | [evidence output] |
| AC-XXX | ✅ verified / ⏳ pending / ❌ failed | [method] | [evidence output] |

---

## DoD Verification Results

> One row per Definition-of-Done item of the reviewed story (S-XXX). DoD
> identifiers must match the story's Definition of Done. The audit's QR DoD
> check validates this table structurally: every item needs an identifier and
> a recorded status/evidence cell. Standard format:
> `| DoD Item | Status | Evidence | Date |`.

| DoD Item | Status | Evidence | Date |
|----------|--------|----------|------|
| DoD-XXX | ✅ passed / ❌ failed | [evidence] | [YYYY-MM-DD] |
| DoD-XXX | ✅ passed / ❌ failed | [evidence] | [YYYY-MM-DD] |

---

## Documentary Checks (Manual Review)

### Code Review
- **Reviewer(s):** [@username1, @username2]
- **Review date:** [YYYY-MM-DD]
- **Comments (summary):**
  - [Important feedback 1]
  - [Important feedback 2]
  - [Important feedback 3]
- **Code quality:**
  - Readability: ✓ Good / ⚠ Fair / ✗ Poor
  - Maintainability: ✓ Good / ⚠ Fair / ✗ Poor
  - Design patterns: ✓ Appropriate / ⚠ Could improve / ✗ Problematic
- **Approval:** ✓ APPROVED / ⚠ APPROVED WITH COMMENTS / ✗ CHANGES REQUESTED
- **Rationale:** [Approval/rejection rationale]

### Documentation
- **Code comments:** ✓ Sufficient / ⚠ Incomplete / ✗ None
- **API documentation:** ✓ Updated / ⚠ Partial / ✗ Missing
- **README/guides:** ✓ Updated / ⚠ Partial / ✗ Missing
- **Changelog:** ✓ Added / ✗ Missing
- **Status:** ✓ COMPLETE / ⚠ NEEDS WORK / ✗ MISSING

### Breaking Changes
- **Breaking change present:** ✓ Yes / ✗ No
- **Migration plan:** [How migration will be done if any]
  - [Step 1]
  - [Step 2]
- **Deprecation notice:** [When the old API will be removed if any]
- **Backward compatibility:** ✓ Preserved / ⚠ Partial / ✗ Broken

### Technical Debt
- **New debt added:** ✓ Yes / ✗ No
- **Debt details:**
  - [Debt 1]: [Description] — [Why added, TODO reference]
  - [Debt 2]: [Description] — [Why added, TODO reference]
- **Debt recorded:** ✓ Yes (`docs/development/tech-debt.md`) / ✗ No

---

## Decision

- **Decision:** APPROVED | REJECTED | REVISED → [Rationale]
- **Rejection reason (if any):**
  - [Reason 1: low test coverage]
  - [Reason 2: security issue]
  - [Reason 3: code review requested changes]
- **Next step:** merge | revision required | plan deploy

---

## Checklist (Gate 3 Check)

### Mechanical (automatic, mandatory)
- [ ] Test coverage >= 80%
- [ ] All tests passed (unit, integration, e2e)
- [ ] Linter and formatter clean
- [ ] Security scan clean (no known vulnerability)
- [ ] No performance regression
- [ ] AC and DoD verification results tables present (identifier + evidence per item)

### Documentary (manual review, mandatory)
- [ ] At least one reviewer approved
- [ ] Code quality acceptable
- [ ] Documentation updated
- [ ] Migration plan ready if breaking change
- [ ] Technical debt recorded (if any)

### Merge Criteria
- [ ] All mechanical checks PASS
- [ ] At least one code review APPROVED
- [ ] Documentation COMPLETE or NEEDS WORK (minor gaps acceptable)
- [ ] Decision: APPROVED

**Note:** If any mechanical or critical documentary check fails, the merge is blocked.
