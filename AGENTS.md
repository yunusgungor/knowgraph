# KnowGraph — Agent Memory

## Project overview
KnowGraph is a code-knowledge graph tool with an MCP server interface. It indexes
source code (via the Joern CLI) into a graph store and answers security/code
queries. Python 3.10–3.13 supported.

## Key facts
- `__version__` lives in `knowgraph/version.py` (currently `1.0.0`).
- `CURRENT_API_VERSION` in `knowgraph/shared/versioning.py` is derived from
  `__version__` — keep them in sync by editing only `knowgraph/version.py`.
- Coverage threshold is defined ONCE in `pytest.ini` (`--cov-fail-under=3`).
  `pyproject.toml`'s `[tool.pytest.ini_options]` deliberately does NOT set a
  threshold (pytest.ini takes precedence). Keep it this way.

## Dependencies / version pins
- `mcp` MUST stay `<2.0`. MCP 2.0 removed the decorator-based Server API that
  `knowgraph/adapters/mcp/server.py` relies on. Pinned in `pyproject.toml`.
- `pydantic-settings` is required by `knowgraph/config.py` (`BaseSettings`).

## Testing
- Run full suite (CI-equivalent): `pytest -v --cov=knowgraph --cov-report=xml`
- `pytest.ini` sets `asyncio_mode = auto` — async test funcs need no
  `@pytest.mark.asyncio` marker.
- Joern CLI is an external dependency. Tests that require it are guarded by the
  `requires_joern` marker defined in `tests/conftest.py` (module-level
  `pytestmark = requires_joern`). They skip when Joern is absent. Do NOT remove
  this guard.
- **Exception:** `tests/test_mcp_e2e.py` is permanently skipped via
  `pytest.mark.skip` (NOT `requires_joern`). It targets a legacy MCP methods
  API that no longer exists: `methods.handle_query()` was removed,
  `index_graph()` changed from a single dict arg to keyword args, and it
  instantiates the abstract `IntelligenceProvider`. With `requires_joern` alone
  it would run (and fail with TypeError/AttributeError) once Joern is installed
  in CI. The up-to-date equivalent lives in `test_mcp_server_e2e.py`. If this
  suite is revived it must be rewritten against the current API.
- Test artifacts (`test_mcp_graphstore/`, `tests/test_e2e_graphstore/`,
  `tests/test_graphs/`, `bookmarks.db`, `.indexing_cache/`) are gitignored.
  Prefer `tmp_path` in new tests; don't write graph stores into the worktree.

## Lint / type checks (CI gates)
- `ruff check .` — must pass.
- `mypy .` — must pass. `python_version = "3.12"` in `[tool.mypy]` is
  intentional: numpy 2.x ships stubs using 3.12+ `type` statements that mypy
  cannot parse when targeting 3.10. Runtime 3.10/3.11 compat is still verified
  by the CI pytest matrix; mypy is static-only here.
- mypy `disable_error_code` list is intentionally permissive — don't tighten
  without running the full suite.

## Known gotchas
- `knowgraph/application/indexing/graph_builder.py`: `asyncio.gather(...,
  return_exceptions=True)` returns `Any | BaseException`; filter with
  `isinstance(m, BaseException)` (not `Exception`) so mypy narrows correctly.
- `knowgraph/core/joern/provider.py`: `raw` must be assigned inside the
  `for item in result.results` loop before use (was an F821 undefined name).
- Hardcoded developer paths (`/Users/yunusgungor/...`) were removed; always use
  `Path(__file__).resolve().parent.parent / ...` for repo-relative paths in tests.

## MCP / CLI conventions
- **Graph-store path argument** is uniformly named `graph_path` across MCP tools.
- **Source/input path argument** has two accepted names: `knowgraph_index`
  uses `input_path` (canonical) and `knowgraph_generate_cpg` uses `source_path`
  (canonical). Each accepts the other as a backward-compatible alias, so callers
  may use either name. The tool `inputSchema` declares `required: []` for these
  two tools on purpose — validation lives in the handler
  (`validate_required_argument` / explicit checks) so the alias can resolve
  before the "required" check. Do not re-add `input_path`/`source_path` to the
  schema `required` list, or the alias will be rejected at schema validation.
- **`version rollback`** prompts for confirmation only when stdin is a TTY. In
  non-interactive/CI shells it aborts with a clear message unless `--force` is
  passed. `--force` both skips the prompt and bypasses validation checks.
