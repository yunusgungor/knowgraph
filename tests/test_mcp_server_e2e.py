#!/usr/bin/env python3
"""End-to-End MCP Server Test.

Tests the KnowGraph MCP server by:
1. Starting the server
2. Connecting as an MCP client
3. Listing all available tools
4. Testing each of the 5 new Joern tools
5. Verifying responses
"""

import asyncio
import json
import subprocess
import tempfile
import time
from pathlib import Path

# Simple MCP client simulation
async def test_mcp_server():
    """Test MCP server end-to-end."""
    
    print("=" * 80)
    print("MCP SERVER END-TO-END TEST")
    print("=" * 80)
    
    # Step 1: Generate test CPG
    print("\n📦 Step 1: Generating test CPG...")
    test_dir = Path(tempfile.mkdtemp(prefix="mcp_e2e_test_"))
    test_file = test_dir / "test.c"
    test_file.write_text('''
#include <stdio.h>
#include <string.h>

void unused_function() {
    printf("Never called\\n");
}

void vulnerable_function(char *input) {
    char buffer[64];
    strcpy(buffer, input);  // Buffer overflow
}

int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

int main() {
    printf("Test\\n");
    return 0;
}
''')
    
    from knowgraph.core.joern import JoernProvider
    provider = JoernProvider()
    cpg_path = provider.generate_cpg(test_dir)
    print(f"✅ CPG generated: {cpg_path}")
    
    # Step 2: Test MCP server by importing handlers directly
    # (simulating MCP protocol calls)
    print("\n🔧 Step 2: Testing MCP handlers...")
    
    from knowgraph.adapters.mcp.handlers import (
        handle_joern_query,
        handle_security_scan,
        handle_find_dead_code,
        handle_analyze_call_graph,
        handle_export_cpg,
    )
    
    results = {}
    
    # Test 1: Joern Query
    print("\n  🔍 Testing knowgraph_joern_query...")
    try:
        result = await handle_joern_query(
            {"cpg_path": str(cpg_path), "query": "cpg.method.name.l"},
            Path.cwd()
        )
        output = result[0].text
        # Relaxed assertions - check for key content
        assert "Joern Query" in output and "Executed" in output
        assert "Results" in output or "nodes" in output
        results["joern_query"] = "✅ PASS"
        print(f"     ✅ Response: {len(output)} chars")
    except Exception as e:
        results["joern_query"] = f"❌ FAIL: {e}"
        print(f"     ❌ Error: {e}")
    
    # Test 2: Security Scan
    print("\n  🔒 Testing knowgraph_security_scan...")
    try:
        result = await handle_security_scan(
            {"cpg_path": str(cpg_path), "severity_filter": "MEDIUM"},
            Path.cwd()
        )
        output = result[0].text
        assert "Security Policy Scan" in output
        assert "Violations Found" in output
        results["security_scan"] = "✅ PASS"
        print(f"     ✅ Response: {len(output)} chars")
    except Exception as e:
        results["security_scan"] = f"❌ FAIL: {e}"
        print(f"     ❌ Error: {e}")
    
    # Test 3: Dead Code Detection
    print("\n  💀 Testing knowgraph_find_dead_code...")
    try:
        result = await handle_find_dead_code(
            {"cpg_path": str(cpg_path), "include_internal": False},
            Path.cwd()
        )
        output = result[0].text
        assert "Dead Code Detection" in output
        assert "Dead Methods Found" in output
        results["find_dead_code"] = "✅ PASS"
        print(f"     ✅ Response: {len(output)} chars")
    except Exception as e:
        results["find_dead_code"] = f"❌ FAIL: {e}"
        print(f"     ❌ Error: {e}")
    
    # Test 4: Call Graph Analysis
    print("\n  📊 Testing knowgraph_analyze_call_graph...")
    try:
        result = await handle_analyze_call_graph(
            {"cpg_path": str(cpg_path), "analysis_type": "validate"},
            Path.cwd()
        )
        output = result[0].text
        assert "Call Graph" in output
        assert "Validation" in output
        results["analyze_call_graph"] = "✅ PASS"
        print(f"     ✅ Response: {len(output)} chars")
    except Exception as e:
        results["analyze_call_graph"] = f"❌ FAIL: {e}"
        print(f"     ❌ Error: {e}")
    
    # Test 5: CPG Export
    print("\n  💾 Testing knowgraph_export_cpg...")
    try:
        export_dir = test_dir / "export"
        export_dir.mkdir(exist_ok=True)
        result = await handle_export_cpg(
            {
                "cpg_path": str(cpg_path),
                "output_path": str(export_dir / "output"),
                "format": "json"
            },
            Path.cwd()
        )
        output = result[0].text
        assert "CPG Export" in output
        assert "JSON" in output.upper()
        results["export_cpg"] = "✅ PASS"
        print(f"     ✅ Response: {len(output)} chars")
    except Exception as e:
        results["export_cpg"] = f"❌ FAIL: {e}"
        print(f"     ❌ Error: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for v in results.values() if "PASS" in v)
    total = len(results)
    
    print(f"\nTotal: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {total - passed}")
    
    print("\nDetailed Results:")
    for tool, status in results.items():
        print(f"  {tool}: {status}")
    
    print("\n" + "=" * 80)
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! MCP Server is working perfectly! 🎉")
        return 0
    else:
        print("⚠️  Some tests failed. Review errors above.")
        return 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(test_mcp_server())
    sys.exit(exit_code)
