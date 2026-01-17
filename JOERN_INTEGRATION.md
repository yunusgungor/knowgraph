# KnowGraph Joern Integration

**Status:** ✅ 100% Complete (v1.4.0)

KnowGraph includes complete Joern Code Property Graph integration for advanced static code analysis.

## Quick Start

\`\`\`bash
# Enable Joern features
export KNOWGRAPH_CPG_NODES_ENABLED=true

# Index code
knowgraph index ./my_project --output ./graph
\`\`\`

## Features

- ✅ CPG generation (28 languages)
- ✅ Security vulnerability detection
- ✅ Dead code detection
- ✅ Call graph analysis
- ✅ Policy-based security validation
- ✅ Interactive REPL
- ✅ Multiple export formats

## Documentation

See `JOERN_USAGE.md` for complete documentation.

## Quick Examples

### Security Scan
\`\`\`python
from knowgraph.application.security.policy_engine import PolicyEngine

engine = PolicyEngine()
violations = engine.validate_policies(cpg_path)
\`\`\`

### Dead Code Detection
\`\`\`python
from knowgraph.application.analysis.dominance_analyzer import DominanceAnalyzer

analyzer = DominanceAnalyzer()
dead_code = analyzer.find_dead_code(cpg_path)
\`\`\`

### Interactive Exploration
\`\`\`python
from knowgraph.application.analysis.joern_repl import JoernREPL

repl = JoernREPL()
repl.start(cpg_path)
\`\`\`

---

**Version:** v1.4.0 (100% Joern Integration)
