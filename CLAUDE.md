# [CLAUDE.md](http://CLAUDE.md)



Communication: All respond in Turkish

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

KnowGraph is a Python MCP server that gives AI coding assistants graph-based code understanding (Joern Code Property Graph + NetworkX knowledge graph + hybrid sparse/dense retrieval). v1.1.1.

## Graph-first workflow (this repo's own rule)

This repo ships a KnowGraph skill (`.claude/skills/knowgraph/SKILL.md`, full reference in `.agent/rules/knowgraph.md`): **query the `knowgraph_*` MCP tools before grepping or reading source** — the graph already traced imports, calls, and dependencies. Key tools: `knowgraph_query` / `knowgraph_batch_query` (retrieval), `knowgraph_analyze_impact` (blast radius), `knowgraph_analyze_call_graph` (callers/chains), `knowgraph_find_dead_code`, `knowgraph_security_scan` (6 policies in `PolicyEngine.POLICIES`, not 10). Graph store is gitignored — run `knowgraph index <path>` once if tools report no graph. `.claude/settings.json` auto re-indexes edited files post-edit via `kg-hooks.py`.

## Commands

```bash
pip install -e ".[dev]"          # dev install; plain install skips Joern (~200MB), add with knowgraph-setup
python -m knowgraph <cmd>        # == `knowgraph` CLI; use when Scripts/ isn't on PATH (Windows)
knowgraph serve                  # start the MCP server
pytest                           # full suite (asyncio_mode=auto; coverage --fail-under=3; needs pytest.ini addopts)
pytest tests/test_query_engine.py # single test file
pytest -m "not slow"             # skip slow tests (also: integration, unit, benchmark markers)
pytest --cov=knowgraph --cov-report=html  # coverage report
ruff check .                     # lint (line-length 100; see per-layer ignores in pyproject)
mypy .                           # type check (excludes tests/, graph_store/; pyright basic mode also configured)
black . && isort .               # format
```

CI (`.github/workflows/ci.yml`): Python 3.10–3.13 matrix + JDK 21 (Joern needs Java), then `pytest --cov`, `ruff check .`, `mypy .`. All three must pass; coverage must not decrease.

Config: copy `.env.example` to `.env`; all settings are `KNOWGRAPH_*` env vars loaded via pydantic-settings in `knowgraph/config.py` (API key/model, perf, memory, query top_k/max_hops).

## Architecture (hexagonal / clean)

```
adapters/       entry points: cli/ (index/query/update/discover/version commands),
                mcp/ (server.py + handlers/ + methods.py — the 21 MCP tools),
                api/ (mostly stub)
application/    use cases: querying/ (query_engine, retriever, impact_analyzer,
                hierarchical_lifting, context_assembly), indexing/ (graph_builder),
                security/ (policy_engine, taint_analyzer), evolution/ (incremental_update),
                linking/, tagging/, analysis/, analytics/
domain/         pure logic: models/ (Node, Edge), algorithms/ (traversal, centrality,
                graph_validator), claims/ (fact pipeline: dag_planner → entity_resolver
                → traversal_engine → grounding_evaluator + temporal_filter; anti-hallucination),
                intelligence/ (code_entity_extractor, cpg_converter, data_flow_analyzer)
infrastructure/ I/O: storage/ (filesystem, manifest, version_history/rollback/diff),
                parsing/ (chunker, markdown/repo/conversation parsers),
                embedding/ (sparse + dense; sentence-transformers is an optional
                `hybrid` extra — code must degrade to sparse-only without it),
                search/ (sparse/dense indexes), joern via core/joern (manager/process/provider),
                detection/ (project root: git → markers → LLM → cwd)
core/           joern/ lifecycle + models/ (download under ~/.knowgraph)
shared/         cross-cutting resilience: circuit_breaker, rate_limiter, throttle, retries (tenacity)
```

Request flow: `adapters` → `application` services → `domain` logic → `infrastructure` (NetworkX graph persisted in `graphstore/` with manifest + SHA-1 integrity + version history). Dependency rule: inner layers never import outer ones.

Commits follow conventional commits (`feat:`, `fix:`, `docs:`, …); user-facing changes update `docs/USER_GUIDE.md`, architectural changes update `docs/ARCHITECTURE.md`.
