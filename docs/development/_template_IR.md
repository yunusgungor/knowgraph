# Implementation Readiness: IR-XXX — [Short Title]

> This template is used for Implementation Readiness (IR) records.
> Represents Development Gate 1: checks whether research findings are ready for development.

## Implementation Readiness: IR-XXX — [Short title]

- **Date:** [YYYY-MM-DD]
- **Status:** preparing | READY | INCOMPLETE
- **Research inputs:** [E/R/D/C-id list]
  - Example: E-001 (BFS optimization), D-005 (user flow design), R-010 (user needs finding)
- **Design documents:** [PRD/UX/architecture file references]
  - PRD: [file path or "none"]
  - UX Spec: [file path or "none"]
  - Architecture Plan: [file path or "none"]
- **Success criteria:** [What counts as success]
  - Functional: [Feature works fully, test coverage 80%+]
  - Non-functional: [Performance target, security standard]
  - User: [User acceptance criteria]
- **Technical dependencies:** [APIs, libraries, infrastructure]
  - APIs: [which APIs needed, available?]
  - Libraries: [new dependencies, versions]
  - Infrastructure: [database, cache, queue ready?]
  - External services: [3rd party integrations]
- **Risk assessment:** [Known risks + mitigation plan]
  - Risk 1: [description] → Mitigation: [how to reduce]
  - Risk 2: [description] → Mitigation: [how to reduce]
- **Gaps:** [If incomplete, what's missing and how to complete]
  - [Gap item 1] → [Research mode: A/B/C/D] → [Estimated time]
  - [Gap item 2] → [Research mode: A/B/C/D] → [Estimated time]
- **Decision:** READY | INCOMPLETE → [Rationale]
- **Next step:** proceed to sprint planning | return to research: [which mode, which question]

---

## Notes

- **READY:** All inputs complete, dependencies ready, sprint can be planned
- **INCOMPLETE:** Gaps identified, research plan exists for each gap
- If gaps exist, the sprint does not start; return to the research wing first
- This record is the "entry gate" of the development wing: research → development transition

---

## Checklist (Gate 1 Check)

- [ ] At least one approved research record exists (E/R/D/C-id)
- [ ] PRD or story defined
- [ ] UX spec ready (if needed)
- [ ] Architecture plan ready (if needed)
- [ ] Success criteria clear and measurable
- [ ] Technical dependencies identified
- [ ] Risk assessment done
- [ ] Plan exists for gaps (if any)
