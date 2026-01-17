"""
Test scenarios for taint analysis.

These tests verify that KnowGraph can detect security vulnerabilities
by tracing data flow from sources to sinks.
"""

import pytest
from pathlib import Path


@pytest.fixture
def vulnerable_app_graph():
    """Index vulnerable Flask app and return graph path."""
    import asyncio
    from knowgraph.adapters.cli.index_command import run_index
    
    fixture_path = Path(__file__).parent / "fixtures" / "vulnerable_app.py"
    graph_path = Path(__file__).parent / "test_graphs" / "vulnerable_app"
    
    # Patch config to force Joern usage for this test
    import knowgraph.domain.intelligence.code_analyzer as ca_module
    import knowgraph.config as config_module
    from unittest.mock import patch

    # Force enable CPG nodes and override language checks
    with patch.object(config_module, 'CPG_NODES_ENABLED', True), \
         patch.object(config_module, 'JOERN_ENABLED', True), \
         patch.object(ca_module, 'JOERN_ENABLED', True), \
         patch.object(ca_module, 'JOERN_FAST_LANGUAGES', []), \
         patch.object(ca_module, 'JOERN_MIN_FILE_SIZE', 0):
        
        # Index the vulnerable code
        # Use asyncio.run + run_index helper
        asyncio.run(
            run_index(
                input_path=str(fixture_path),
                output_path=str(graph_path),
            )
        )
    
    return str(graph_path)


class TestSQLInjectionDetection:
    """Test SQL injection vulnerability detection."""
    
    def test_detect_sql_injection_in_login(self, vulnerable_app_graph):
        """Should detect SQL injection in vulnerable_login()."""
        from knowgraph.application.security.taint_analyzer import TaintAnalyzer
        
        analyzer = TaintAnalyzer(vulnerable_app_graph)
        
        # Find SQL injection vulnerabilities
        vulns = analyzer.find_vulnerabilities(
            source_patterns=["request.form"],
            sink_patterns=["cursor.execute", ".execute("],
        )
        
        # Should find at least 1 SQL injection
        assert len(vulns) > 0
        
        # Verify it's in vulnerable_login function
        sql_injection = next(
            v for v in vulns 
            if "vulnerable_login" in v.path_description
        )
        
        assert sql_injection.vulnerability_type == "SQL Injection"
        assert sql_injection.severity == "Critical"
        assert "request.form" in sql_injection.source_description
        assert "execute" in sql_injection.sink_description
        
    def test_detect_sql_injection_in_search(self, vulnerable_app_graph):
        """Should detect SQL injection via GET parameter."""
        from knowgraph.application.security.taint_analyzer import TaintAnalyzer
        
        analyzer = TaintAnalyzer(vulnerable_app_graph)
        
        vulns = analyzer.find_vulnerabilities(
            source_patterns=["request.args"],
            sink_patterns=["execute("],
        )
        
        # Should find search endpoint vulnerability
        assert any("vulnerable_search" in v.path_description for v in vulns)
        
    def test_safe_login_no_vulnerability(self, vulnerable_app_graph):
        """Should NOT flag safe_login as vulnerable."""
        from knowgraph.application.security.taint_analyzer import TaintAnalyzer
        
        analyzer = TaintAnalyzer(vulnerable_app_graph)
        
        # Analyze safe_login specifically
        vulns = analyzer.find_vulnerabilities()
        
        # Safe login should not be in results
        assert not any("safe_login" in v.path_description for v in vulns)


class TestXSSDetection:
    """Test Cross-Site Scripting detection."""
    
    def test_detect_xss_in_render_template_string(self, vulnerable_app_graph):
        """Should detect XSS in vulnerable_xss()."""
        from knowgraph.application.security.taint_analyzer import TaintAnalyzer
        
        analyzer = TaintAnalyzer(vulnerable_app_graph)
        
        vulns = analyzer.find_vulnerabilities(
            source_patterns=["request.args", "request.GET"],
            sink_patterns=["render_template_string", "mark_safe"],
        )
        
        xss_vulns = [v for v in vulns if v.vulnerability_type == "XSS"]
        assert len(xss_vulns) > 0
        assert any("vulnerable_xss" in v.path_description for v in xss_vulns)
        
    def test_detect_stored_xss(self, vulnerable_app_graph):
        """Should detect stored XSS with intermediate function."""
        from knowgraph.application.security.taint_analyzer import TaintAnalyzer
        
        analyzer = TaintAnalyzer(vulnerable_app_graph)
        
        # This tests multi-hop taint flow:
        # request.form -> save_comment() -> HTML rendering
        vulns = analyzer.find_vulnerabilities(
            source_patterns=["request.form"],
            sink_patterns=["return html", "HttpResponse"],
        )
        
        # Should trace through save_comment()
        stored_xss = next(
            (v for v in vulns if "save_comment" in str(v.path)), 
            None
        )
        assert stored_xss is not None


class TestCommandInjectionDetection:
    """Test command injection detection."""
    
    def test_detect_subprocess_injection(self, vulnerable_app_graph):
        """Should detect command injection via subprocess."""
        from knowgraph.application.security.taint_analyzer import TaintAnalyzer
        
        analyzer = TaintAnalyzer(vulnerable_app_graph)
        
        vulns = analyzer.find_vulnerabilities(
            source_patterns=["request.args", "request.form"],
            sink_patterns=["subprocess.call", "os.system"],
        )
        
        cmd_injection = [v for v in vulns if v.vulnerability_type == "Command Injection"]
        assert len(cmd_injection) >= 2  # ping and backup endpoints
        
    def test_path_includes_dangerous_function(self, vulnerable_app_graph):
        """Verify taint path includes subprocess.call."""
        from knowgraph.application.security.taint_analyzer import TaintAnalyzer
        
        analyzer = TaintAnalyzer(vulnerable_app_graph)
        
        vulns = analyzer.find_vulnerabilities(
            source_patterns=["request.args.get('host')"],
            sink_patterns=["subprocess.call"],
        )
        
        assert len(vulns) > 0
        ping_vuln = vulns[0]
        
        # Path should show: request.args -> host variable -> subprocess.call
        assert len(ping_vuln.path) >= 3


class TestPathTraversalDetection:
    """Test path traversal detection."""
    
    def test_detect_file_open_with_user_input(self, vulnerable_app_graph):
        """Should detect path traversal in file operations."""
        from knowgraph.application.security.taint_analyzer import TaintAnalyzer
        
        analyzer = TaintAnalyzer(vulnerable_app_graph)
        
        vulns = analyzer.find_vulnerabilities(
            source_patterns=["request.args"],
            sink_patterns=["open("],
        )
        
        path_traversal = [v for v in vulns if v.vulnerability_type == "Path Traversal"]
        assert len(path_traversal) > 0


class TestDataflowQuery:
    """Test dataflow query API."""
    
    @pytest.mark.asyncio
    async def test_query_dataflow_user_to_database(self, vulnerable_app_graph):
        """Test natural language dataflow query."""
        from knowgraph.application.querying.query_engine import QueryEngine
        
        engine = QueryEngine(graph_store_path=vulnerable_app_graph)
        
        # Natural language query
        result = await engine.query_dataflow(
            source_pattern="user input from request",
            sink_pattern="database query execution",
            max_path_length=10,
        )
        
        assert result.path_count > 0
        assert len(result.paths) > 0
        
        # All paths should have data_flow edges
        for path in result.paths:
            assert len(path) >= 2  # At least source and sink
            
    @pytest.mark.asyncio
    async def test_dataflow_result_to_mermaid(self, vulnerable_app_graph):
        """Test Mermaid diagram generation."""
        from knowgraph.application.querying.query_engine import QueryEngine
        
        engine = QueryEngine(graph_store_path=vulnerable_app_graph)
        
        result = await engine.query_dataflow(
            source_pattern="request parameter",
            sink_pattern="SQL execution",
        )
        
        # Should generate Mermaid flowchart
        mermaid = result.to_mermaid()
        
        assert "graph TD" in mermaid or "graph LR" in mermaid
        assert "-->" in mermaid  # Edge syntax


class TestVulnerabilityPatterns:
    """Test vulnerability pattern matching."""
    
    def test_load_predefined_patterns(self):
        """Should load CWE-mapped patterns."""
        from knowgraph.application.security.vulnerability_patterns import (
            VULNERABILITY_PATTERNS,
            VulnerabilityType,
        )
        
        assert VulnerabilityType.SQL_INJECTION in VULNERABILITY_PATTERNS
        assert VulnerabilityType.XSS in VULNERABILITY_PATTERNS
        
        sql_pattern = VULNERABILITY_PATTERNS[VulnerabilityType.SQL_INJECTION]
        assert sql_pattern.cwe_id == "CWE-89"
        assert sql_pattern.severity == "Critical"
        assert len(sql_pattern.sources) > 0
        assert len(sql_pattern.sinks) > 0
        
    def test_pattern_has_sanitizers(self):
        """Patterns should include sanitizer functions."""
        from knowgraph.application.security.vulnerability_patterns import (
            VULNERABILITY_PATTERNS,
            VulnerabilityType,
        )
        
        sql_pattern = VULNERABILITY_PATTERNS[VulnerabilityType.SQL_INJECTION]
        
        # Should have sanitizers (functions that clean data)
        assert len(sql_pattern.sanitizers) > 0
        assert any("escape" in s or "parameter" in s for s in sql_pattern.sanitizers)


class TestPerformance:
    """Test taint analysis performance."""
    
    def test_large_graph_performance(self, vulnerable_app_graph):
        """Taint analysis should complete in reasonable time."""
        import time
        from knowgraph.application.security.taint_analyzer import TaintAnalyzer
        
        analyzer = TaintAnalyzer(vulnerable_app_graph)
        
        start = time.time()
        vulns = analyzer.find_vulnerabilities()
        elapsed = time.time() - start
        
        # Should complete in < 5 seconds for small test fixture
        assert elapsed < 5.0
        
    def test_path_length_limit(self, vulnerable_app_graph):
        """Should respect max path length to avoid explosion."""
        from knowgraph.application.security.taint_analyzer import TaintAnalyzer
        
        analyzer = TaintAnalyzer(vulnerable_app_graph)
        
        # Set very short max depth
        vulns = analyzer.find_vulnerabilities(max_depth=3)
        
        # All paths should be <= 3 hops
        for vuln in vulns:
            assert len(vuln.path) <= 3
