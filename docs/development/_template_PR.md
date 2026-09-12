# Production Readiness: PR-XXX — [Release Name]

> This template is used for Production Readiness (PR) records.
> Represents Development Gate 4: guarantees operational readiness before production deploy.

## Production Readiness: PR-XXX — [Release name]

- **Date:** [YYYY-MM-DD]
- **Status:** preparing | READY | WAITING
- **Release type:** [Major / Minor / Patch / Hotfix]
- **Version:** [v1.2.3]
- **Release scope:** [QR-id list — what goes into this release]
  - QR-001: [Story title]
  - QR-002: [Story title]
  - QR-003: [Story title]

---

## Staging Test

### Deployment
- **Staging environment:** [URL or environment name]
- **Deploy date:** [YYYY-MM-DD HH:MM]
- **Deploy method:** [CI/CD pipeline / manual / script]
- **Deploy duration:** [X minutes]
- **Deploy status:** ✓ SUCCESS / ✗ FAILED

### Smoke Tests
- **Test scenarios:**
  - [Scenario 1]: [Description] → ✓ PASS / ✗ FAIL
  - [Scenario 2]: [Description] → ✓ PASS / ✗ FAIL
  - [Scenario 3]: [Description] → ✓ PASS / ✗ FAIL
- **End-to-end test:** ✓ PASS / ✗ FAIL
- **Critical path test:** ✓ PASS / ✗ FAIL
- **Status:** ✓ ALL PASS / ✗ FAILURES

### Integration Tests (Staging)
- **Database migration:** ✓ SUCCESS / ✗ FAILED
- **External services:** ✓ CONNECTED / ✗ FAILED
- **API endpoints:** [X/Y working]
- **Status:** ✓ ALL SYSTEMS GO / ✗ ISSUES

---

## Rollback Plan

- **Rollback method:** [Blue-green / rolling / instant]
- **Rollback triggers:** [Under what conditions rollback happens]
  - [Trigger 1: error rate > 5%]
  - [Trigger 2: latency > 500ms]
  - [Trigger 3: crash rate > 1%]
- **Rollback duration:** [Estimated X minutes]
- **Rollback steps:**
  1. [Step 1: alarm triggered, stop deploy]
  2. [Step 2: redirect traffic to previous version]
  3. [Step 3: remove new version]
  4. [Step 4: database rollback (if needed)]
  5. [Step 5: smoke test on previous version]
- **Rollback tested:** ✓ Yes (in staging) / ✗ No
- **Database rollback:** [Needed? How?]
  - Migration reversible: ✓ Yes / ✗ No (destructive)
  - Rollback SQL: [File reference if any]

---

## Monitoring and Alerting

### Metrics
- **Business metrics:**
  - [Metric 1: daily active users] → Dashboard: [link]
  - [Metric 2: transaction success rate] → Dashboard: [link]
- **Technical metrics:**
  - [Metric 3: response time] → Dashboard: [link]
  - [Metric 4: error rate] → Dashboard: [link]
  - [Metric 5: CPU/memory usage] → Dashboard: [link]
- **Dashboard URL:** [Production monitoring dashboard link]

### Alerts
- **Critical alerts:**
  - [Alert 1: error rate > 5%] → Channel: [slack/pagerduty] → Owner: [who]
  - [Alert 2: latency > 1000ms] → Channel: [slack/pagerduty] → Owner: [who]
- **Warning alerts:**
  - [Alert 3: memory > 80%] → Channel: [slack] → Owner: [who]
- **Alerts tested:** ✓ Yes / ✗ No

### Logging
- **Log aggregation:** [Tool: ELK / Splunk / CloudWatch]
- **Log retention:** [X days]
- **Structured logging:** ✓ Yes / ✗ No
- **Log queryability:** ✓ Tested / ✗ Not tested

---

## Feature Flags

- **Feature flags used:** ✓ Yes / ✗ No
- **Flag plan:**
  - [Feature 1]: [flag name] → Rollout: [%0 → %10 → %50 → %100]
  - [Feature 2]: [flag name] → Rollout: [%0 → %100 (instant)]
- **Kill switch:** ✓ Present / ✗ Absent
  - [Which features can be turned off instantly]
- **Gradual rollout duration:** [X hours/days]

---

## Runbook

### Deploy Steps
1. [Pre-deploy: database backup]
2. [Pre-deploy: notify team]
3. [Deploy: CI/CD pipeline trigger]
4. [Deploy: wait for green deployment]
5. [Post-deploy: smoke test]
6. [Post-deploy: monitor 30 min]
7. [Post-deploy: notify completion]

### Troubleshooting
- **Common issues and solutions:**
  - [Issue 1]: [Description] → Solution: [steps]
  - [Issue 2]: [Description] → Solution: [steps]
- **Runbook URL:** [Detailed runbook wiki/doc link]

### Rollback Steps (Detailed)
[Details of what was written in the Rollback Plan section, including commands]

---

## Incident Response

### Communication Plan
- **Incident lead:** [Name, contact]
- **Technical lead:** [Name, contact]
- **Stakeholder communication:** [Channel: email/slack]
- **On-call roster:** [PagerDuty/Opsgenie link or list]

### Incident Severity
- **SEV1 (Critical):** [Description, SLA: X minutes response]
- **SEV2 (Major):** [Description, SLA: Y hours response]
- **SEV3 (Minor):** [Description, SLA: Z days response]

### Post-Mortem
- **Post-mortem required:** [Mandatory for SEV1/SEV2]
- **Template:** `docs/development/incidents/PM-XXX.md`

---

## Deploy Window

- **Planned deploy time:** [YYYY-MM-DD HH:MM UTC]
- **Deploy window:** [X hours — deploy + monitoring]
- **Freeze period:** [Days/hours when deploy is not allowed if any]
- **Change approval:** ✓ Approved (by: [name], date: [YYYY-MM-DD]) / ✗ Pending

---

## Decision

- **Decision:** READY | WAITING → [Rationale]
- **Blockers (if any):**
  - [Blocker 1: staging smoke test failed]
  - [Blocker 2: rollback plan incomplete]
- **Next step:** production deploy | complete the gaps

---

## Deploy Result (Post-Deploy)

> This section is filled after deploy

- **Deploy date:** [YYYY-MM-DD HH:MM UTC]
- **Deploy duration:** [X minutes]
- **Deploy status:** ✓ SUCCESS / ✗ FAILED / ⚠ ROLLED BACK
- **Post-deploy metrics (first 1 hour):**
  - Error rate: [%X] (baseline: [%Y])
  - Latency p95: [X ms] (baseline: [Y ms])
  - Traffic: [X req/sec] (baseline: [Y req/sec])
- **Incident if any:** [PM-XXX reference]
- **Notes:** [Lessons learned during deploy, improvement suggestions]

---

## Checklist (Gate 4 Check)

### Staging
- [ ] Successfully deployed to staging
- [ ] Smoke tests passed
- [ ] End-to-end integration test passed

### Rollback
- [ ] Rollback plan ready and clear
- [ ] Rollback triggers defined
- [ ] Rollback tested in staging (or dry-run)
- [ ] Database rollback plan exists (if needed)

### Monitoring
- [ ] Dashboard set up and accessible
- [ ] Critical alerts set up and tested
- [ ] Logging configured and query tested

### Feature Flags (if any)
- [ ] Feature flag plan defined
- [ ] Kill switch ready
- [ ] Gradual rollout strategy clear

### Runbook
- [ ] Deploy steps documented
- [ ] Troubleshooting guide ready
- [ ] Rollback steps written in detail

### Incident Response
- [ ] On-call roster up to date
- [ ] Communication channels defined
- [ ] Incident severity and SLA clear

### Approval
- [ ] Change approval obtained
- [ ] Deploy window determined
- [ ] Stakeholders informed

**Deploy Criteria:** All checklist items must be completed. If no rollback plan or missing monitoring, deploy is blocked.
