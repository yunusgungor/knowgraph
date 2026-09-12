# Mode B/D — Research Records

This template covers Mode B (qualitative) and Mode D (contextual) research records.
For Mode A (quantitative/empirical) → `docs/experiments/_template.md`
For Mode C (design) → `docs/design/_template.md`
Manifesto: `docs/bmad/research-methodology.md`.

## Output Location

Mode B/D outputs land in `docs/research/`:

| Skill | Output Path | File Pattern |
|-------|-------------|-------------|
| `bmad-domain-research` | `docs/research/` | `domain-{topic_slug}-research-{date}.md` |
| `bmad-market-research` | `docs/research/` | `market-{topic_slug}-research-{date}.md` |
| `bmad-technical-research` | `docs/research/` | `technical-{topic_slug}-research-{date}.md` |

## What Goes Where

- **Domain Research** (`docs/research/domain-*.md`): Literature reviews, expert interviews, case analysis
- **Market Research** (`docs/research/market-*.md`): Market sizing, competitor analysis, competitive landscape
- **Technical Research** (`docs/research/technical-*.md`): Technology evaluation, architecture research, feasibility studies

## Running Mode B/D Skills

```
/domain-research    → creates docs/research/domain-{topic}-research-{date}.md
/market-research    → creates docs/research/market-{topic}-research-{date}.md
/technical-research → creates docs/research/technical-{topic}-research-{date}.md
```
