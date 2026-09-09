# Code Docs Index

Structured documentation system used to remember project history and generate new knowledge.

## Categories

### [Decisions](./decisions/) — 0 records

### [Patterns](./patterns/) — 0 records

### [Learnings](./learnings/) — 0 records

### [API Usages](./api/) — 0 records

### [Troubleshooting](./troubleshooting/) — 0 records

### [Pending Items](./pending/) — 3 records
- [TODO: loji/metodoloji/1.0.0/hooks/engine](./pending/X-001-todo-lojimetodoloji100hooksengine.md)
- [TODO: loji/metodoloji/1.0.0/hooks/engine](./pending/X-002-todo-lojimetodoloji100hooksengine.md)
- [TODO: loji/metodoloji/1.0.0/hooks/engine](./pending/X-003-todo-lojimetodoloji100hooksengine.md)

## Automatic Generation

These files are generated automatically by hooks:
- **Audit hook**: Detects important events (experiment approval, architecture change, error resolution)
- **Guard hook**: Generates a learning doc after experiment approval
- **Skill**: Manual recall and recording via `bmad-code-docs`

## Search

- By tag: `recall_by_tag("auth")`
- By experiment ID: `recall_by_experiment("E-001")`
- By category: list in the `docs/code-docs/decisions/` folder

## Automatic Loading

Relevant docs are loaded automatically at task start:

```python
# Based on task context
context = load_context_for_task("Run the guard hook auth test")

# Recent docs
recent = load_recent_docs(n=5)

# Pending items
pending = load_pending_docs()
```

## Last Update

Updated automatically — no manual editing needed.