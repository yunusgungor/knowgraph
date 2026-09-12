# Mode C — Design Records

This template covers Mode C (design) records: PRDs, UX designs, and architecture spines.
For Mode A (quantitative/empirical) → `docs/experiments/_template.md`
For Mode B/D (qualitative/contextual) → `docs/research/_template.md`
Manifesto: `docs/bmad/research-methodology.md`.

## Output Locations

Mode C outputs land in `docs/design/`:

| Skill | Output Path | Run Folder Pattern |
|-------|-------------|-------------------|
| `bmad-prd` | `docs/design/prds/` | `prd-{project_name}-{date}` |
| `bmad-ux` | `docs/design/ux-designs/` | `ux-{project_name}-{date}` |
| `bmad-architecture` | `docs/design/architecture/` | `architecture-{project_name}-{date}` |

Each skill creates its own run folder inside the corresponding subdirectory.

## What Goes Where

- **PRD** (`docs/design/prds/`): Product requirements document, optional addendum, validation report
- **UX Design** (`docs/design/ux-designs/`): DESIGN.md, EXPERIENCE.md, wireframes, mockups, validation report
- **Architecture** (`docs/design/architecture/`): ARCHITECTURE-SPINE.md, decision records, diagrams

## Running Mode C Skills

```
/bmad-prd          → creates docs/design/prds/prd-{project}-{date}/
/bmad-ux           → creates docs/design/ux-designs/ux-{project}-{date}/
/bmad-architecture → creates docs/design/architecture/architecture-{project}-{date}/
```
