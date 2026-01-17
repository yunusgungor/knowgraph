# Migration Guide: v0.7.x to v0.8.0

This guide covers the migration process for upgrading KnowGraph to v0.8.0, which introduces the **Joern Code Analysis Engine**.

## 🚀 Overview

v0.8.0 uses a hybrid analysis approach (AST + Joern CPG). The internal graph structure has been enhanced to support new edge types (`call`, `data_flow`).

### Breaking Changes

*   **Graph Schema**: The node and edge attributes have been expanded. Old graphs (v0.7.x) are **not compatible** and must be re-indexed.
*   **Configuration**: New environment variables for Joern (optional, as defaults work).
*   **Python Version**: Strictly requires Python 3.10+.

---

## 🛠️ Step-by-Step Migration

### 1. Backup Existing Data

Since v0.8.0 requires re-indexing, you should backup your existing graph store if you want to keep the old text-based index for reference.

```bash
cp -r ./graphstore ./graphstore_v0.7_backup
```

### 2. Upgrade Package

Upgrade KnowGraph to the latest version.

```bash
pip install --upgrade knowgraph
```

### 3. Verify Joern Installation

v0.8.0 automatically installs the Joern CLI wrapper. Verify it works:

```bash
# This downloads/verifies the Joern binary
knowgraph-setup-joern
```

### 4. Re-Index Your Codebase

You must run a full re-indexing operation to generate the Code Property Graphs (CPG) and enable deep code analysis.

```bash
# Clean start (recommended)
rm -rf ./graphstore

# Re-index
knowgraph index /path/to/your/project
```

> **Note**: The first run will take longer (~30-60s) as it generates CPGs. Subsequent runs will be sub-second thanks to CPG caching.

---

## 🔄 Configuration Changes

Review your `.env` or configuration if you have custom settings.

### New Variables (Optional)

```bash
# Force disable Joern (use only AST)
KNOWGRAPH_JOERN_ENABLED=false

# Custom Joern path (if not using auto-install)
KNOWGRAPH_JOERN_PATH=/usr/local/bin/joern
```

---

## 🔍 Verification

After indexing, run a test query to confirm Joern is active:

```bash
knowgraph query "find security vulnerabilities"
```

If the system routes this to `JOERN_SECURITY_SCAN`, your migration is complete!
