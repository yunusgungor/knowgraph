#!/usr/bin/env python3
"""Simplified MCP end-to-end test - tests actual integration."""

import sys

sys.path.insert(0, "/Users/yunusgungor/knowrag")

import asyncio
import tempfile
from pathlib import Path


async def test_code_integration_e2e():
    """Test code integration through actual code path."""
    print("🧪 END-TO-END CODE INTEGRATION TEST")
    print("=" * 70)

    from knowgraph.infrastructure.indexing.code_index_integration import CodeIndexIntegration

    test_dir = Path("/Users/yunusgungor/knowrag/knowgraph/domain/intelligence")

    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "graph"
        graph_path.mkdir()

        print(f"Testing: {test_dir}")
        print()

        integration = CodeIndexIntegration()
        result = integration.process_code_directory(test_dir, graph_path)

        print("RESULTS:")
        print("-" * 70)
        print(f"Code files detected:     {result.get('code_files_detected', 0)}")
        print(f"CPG generated:           {result.get('cpg_generated', False)}")
        print(f"Entities extracted:      {result.get('entities_extracted', 0)}")
        print(f"Call edges:              {result.get('call_edges_extracted', 0)}")
        print(f"Data flows:              {result.get('data_flows_found', 0)}")
        print(f"Doc links:               {result.get('doc_links_found', 0)}")
        print(f"CPG cached:              {result.get('cpg_cached', False)}")
        print(f"Parallel generation:     {result.get('parallel_generation', False)}")
        print(f"From cache:              {result.get('cpg_from_cache', False)}")

        print()
        print("FEATURE VERIFICATION:")
        print("-" * 70)

        checks = [
            ("Code Detection", result.get("code_files_detected", 0) > 0),
            ("CPG Generation", result.get("cpg_generated", False)),
            ("Entity Extraction", result.get("entities_extracted", 0) > 0),
            ("Call Graph", result.get("call_edges_extracted", 0) > 0),
            ("Data Flow", result.get("data_flows_found", 0) > 0),
            ("CPG Caching", result.get("cpg_cached", False)),
        ]

        all_passed = True
        for name, status in checks:
            icon = "✅" if status else "❌"
            print(f"{icon} {name:20} : {'WORKING' if status else 'FAILED'}")
            if not status:
                all_passed = False

        print()
        print("=" * 70)

        if all_passed:
            print("🎉 ALL FEATURES WORKING IN PRODUCTION!")
            print("✅ System is PRODUCTION READY")
            return 0
        else:
            print("⚠️  Some features not working")
            return 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_code_integration_e2e())
    exit(exit_code)
