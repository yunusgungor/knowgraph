# Technical Debt Tracking

> This file tracks technical debt accumulated in the project and the repayment plan.
> A time-box should be reserved for technical debt in every sprint.

**Last updated:** 2026-08-26

> **2026-08-26 — SkillOpt tech-debt integration completed.** With 12 commits (957e5c2..8f2eb93),
> all debt in all 6 manifests was paid (TD-001/002/003/010/011/012), the SkillOpt `techdebt` task
> category was added (6/6 benchmarks), `scripts/check-techdebt.sh` inventory checks mechanically in
> 5 sections, baseline.json is in the repo (66/66), 151 tests PASS, 3/3 negtest. Active
> debt: **0**. The next debt cycle will start with new P3 records.

---

## Active Technical Debts

### Critical Priority (P0)

| ID | Description | Why Added | Date Added | Impact | Owner | Target Sprint |
|----|-------|---------------|---------------|------|--------|--------------|
| —    | —     | —             | —             | —    | —      | —            |

### High Priority (P1)

| ID | Description | Why Added | Date Added | Impact | Owner | Target Sprint |
|----|-------|---------------|---------------|------|--------|--------------|
| —    | —     | —             | —             | —    | —      | —            |

### Medium Priority (P2)

| ID | Description | Why Added | Date Added | Impact | Owner | Target Sprint |
|----|-------|---------------|---------------|------|--------|--------------|
| —    | —     | —             | —             | —    | —      | —            |

### Low Priority (P3)

| ID | Description | Why Added | Date Added | Impact | Owner | Target Sprint |
|----|-------|---------------|---------------|------|--------|--------------|
| — | — | — | — | — | — | — |

---

## Paid Debts (Completed)

| ID | Description | Solution | Completion Date | Sprint | PR/QR |
|----|-------|-------|-------------------|--------|-------|
| TD-001 | `test_marketplace_json_content` (bmad-module-builder) marked as broken test — still listed as P0 in the manifest | Verified with pytest on 2026-08-26: 9/9 test_scaffold_standalone_module + 7/7 test_scaffold_setup_skill + 21/21 test_validate_module (total 37/37) PASS. Scaffold produces `marketplace_name = f"bmad-{args.module_code}"`, test expects `bmad-exc` — compatible. Debt record was old (2026-08-19) and scaffold had been working correctly since the initial commit; the record was incorrectly updated | 2026-08-26 | — | 1fcc9fd |
| TD-003 | Test suites of other installed skills (except bmad-workflow-builder) had never been run | Verified with pytest on 2026-08-26 — 9 test files, **114/114 PASS**: bmad-architecture (28) + bmad-brainstorming (27) + bmad-customize (13) + bmad-eval-runner (4+11=15) + bmad-forge-idea (16) + bmad-workflow-builder (2+7+6=15). All active skill tests deterministic and green | 2026-08-26 | — | 1fcc9fd |
| TD-002 | Monitor false-positive: `tech-debt.md` template placeholders were mistaken for real debt (`sprint-status.sh`/`tech-debt-monitor.sh` showed "4 active debts, P0:1") | `scripts/check-techdebt.sh` 5 sections: (1) template/live identity, (2) active ID unique + sequential, (3) P0 hard limit (<=5), (4) no active/paid overlap, (5) orphan TODO; 3-stage `--negtest`; integrated as `check-plugin.sh §6b` | 2026-08-26 | — | 1de54b1 |
| TD-010 | Windows UTF-8 corruption in all Python scripts (cp1254) | Added `encoding="utf-8", errors="replace"` to `subprocess.run(..., text=True)` calls (14 files, 19 calls) | 2026-08-19 | — | — |
| TD-011 | `check-methodology.sh` §2b bridge check false-positive (KÖPRÜ merge seemed "absent") | Added `encoding="utf-8"` to §2b subprocess; `STATUS: HEALTHY` | 2026-08-19 | — | — |
| TD-012 | SkillOpt API key hard-coded in source (`sk-*` setdefault fallbacks) — security debt + breaking deterministic training | 4 steps: (1) `.env.example` template + `.gitignore` `.env` protection, (2) removed setdefault fallbacks in `optimization/train.py` + `cli.py` + `envs/bmad/adapter.py`, (3) `train._require_llm_env()` errors on missing env in non-`--benchmark` paths, (4) added `check-plugin.sh §6a` 4 sub-checks + 3-stage `--negtest` | 2026-08-26 | — | cf679ea |

---

## Technical Debt Categories

### 1. Code Quality
- **Definition:** Poorly written code, code smells, duplicate code
- **Examples:**
  - Complex functions (high cyclomatic complexity)
  - Dead code (unused functions/classes)
  - Magic numbers (hardcoded constants)
  - God objects (too many responsibilities)

### 2. Test Debt
- **Definition:** Missing tests, flaky tests, low coverage
- **Examples:**
  - Unit test coverage < 80%
  - Missing integration tests
  - Insufficient E2E test coverage
  - Flaky tests (intermittent failures)

### 3. Documentation Debt
- **Definition:** Missing or outdated documentation
- **Examples:**
  - Missing API documentation
  - Insufficient code comments
  - README not up to date
  - Runbook missing or outdated

### 4. Architecture Debt
- **Definition:** Architecture decisions, tight coupling, scalability issues
- **Examples:**
  - Monolith to microservice migration needed
  - Tight coupling (too many dependencies)
  - Database schema normalization issue
  - Scalability bottlenecks

### 5. Infrastructure Debt
- **Definition:** Infrastructure, deployment, monitoring gaps
- **Examples:**
  - Manual deployment steps (missing automation)
  - Insufficient monitoring
  - Missing log aggregation
  - No disaster recovery plan

### 6. Dependency Debt
- **Definition:** Outdated dependencies, security vulnerabilities
- **Examples:**
  - Deprecated libraries
  - Known security vulnerabilities
  - End-of-life technologies

### 7. Performance Debt
- **Definition:** Performance optimizations, memory leaks
- **Examples:**
  - N+1 query problem
  - Memory leak
  - Inefficient algorithm (O(n²) → O(n log n))
  - Missing caching

---

## Technical Debt Metrics

### Current State
- **Total active debt:** [X items]
  - P0 (Critical): [Y items]
  - P1 (High): [Z items]
  - P2 (Medium): [W items]
  - P3 (Low): [V items]
- **Estimated repayment time:** [X sprint / Y weeks]

### Sprint Allocation
- **Technical debt time-box per sprint:** [20% or X story points]
- **Debt paid in the last 3 sprints:** [X items]
- **Debt added in the last 3 sprints:** [Y items]
- **Net debt change:** [X - Y = Z] (positive = debt decreasing, negative = debt increasing)

### Trend
```
Sprint    | New Debt | Paid Debt | Net Change | Total Debt
----------|-----------|-------------|-------------|-------------
SP-001    | 5         | 2           | -3          | 15
SP-002    | 3         | 4           | +1          | 14
SP-003    | 2         | 3           | +1          | 13
```

---

## Repayment Strategy

### Principle: Boy Scout Rule
> "Leave the code cleaner than you found it." Reduce debt by making small improvements in every PR.

### Time-Box Allocation
- **Every sprint:** Reserve 20% capacity for technical debt
- **Critical debt (P0):** Take into the immediate sprint, before features
- **High debt (P1):** Plan within the next 2 sprints
- **Medium/Low debt (P2/P3):** Handle opportunistically (during refactoring)

### Debt Prioritization Criteria
1. **Security risk:** If there is a vulnerability, P0
2. **Production incident risk:** If it could cause an incident, P0/P1
3. **Development speed impact:** If it slows down new feature development, P1
4. **Maintenance cost:** If it continuously produces bugs, P1
5. **Code smell:** If it's just bad code, P2/P3

---

## Debt Addition Rules

### Can Debt Be Added?
- ✓ **Yes:** If a temporary shortcut was taken to deliver quickly (conscious decision)
- ✓ **Yes:** If test coverage was temporarily lowered (with a repayment plan)
- ✗ **No:** If poor quality code is written saying "we'll fix it later" (unacceptable)
- ✗ **No:** If debt is left unrecorded (hidden debt is forbidden)

### Debt Addition Process
1. Identified during QR (Quality Review)
2. Added to `tech-debt.md` (ID, description, rationale, priority)
3. `// TODO: [TD-XXX] ...` comment added in code
4. Target sprint determined (mandatory for P0/P1)

### Debt Limit
- **Hard limit:** If P0 debt count > 5, no new features; pay off debt first
- **Soft limit:** If total active debt > 30, a debt repayment sprint is scheduled

---

## TODO Comment Standard

```python
# TODO: [TD-XXX] <Short description>
# Detail: <What needs to be fixed>
# Added: <YYYY-MM-DD> - <@username>
```

**Example:**
```python
# TODO: [TD-042] BFS algorithm is O(n²), should be optimized to O(n log n)
# Detail: Priority queue implementation using a heap instead of nested loop
# Added: 2026-08-15 - @ahmet
def bfs(graph):
    # Temporary implementation
    pass
```

---

## Review

### Weekly Review
- **Owner:** Tech Lead
- **What:** Newly added debt is reviewed, priorities updated
- **Action:** Critical debt is taken into the sprint

### Monthly Health Check
- **Owner:** Team + Engineering Manager
- **What:** Technical debt metrics reviewed, trend analysis done
- **Action:** Debt repayment strategy adjusted

### Quarterly Audit
- **Owner:** Entire engineering organization
- **What:** All technical debt audited, which ones are still valid
- **Action:** Old/irrelevant debt removed, new ones added

---

## Notes

- Technical debt **cannot be hidden** (development honesty rule 3)
- Technical debt is checked at every QR and recorded if present
- Debt repayment is **as important as feature delivery**
- Principle: not "move fast and break things" but "move at a sustainable pace"

---

## Related Documents

- [Development Methodology](../bmad/development-methodology.md)
- [Quality Review Template](_template_QR.md)
- [Sprint Template](_template_SP.md)
