"""Quick test for Joern integration.

This script verifies the core Joern components are working:
1. JoernProvider initialization (auto-detection)
2. CodeAnalyzer hybrid strategy
3. Language detection
"""

def test_joern_provider_init():
    """Test JoernProvider initialization and auto-detection."""
    print("\n" + "="*60)
    print("Test 1: JoernProvider Initialization")
    print("="*60)
    
    try:
        from knowgraph.core.joern import ExportFormat, JoernCPG, JoernEntity, JoernProvider
        
        provider = JoernProvider()
        print(f"✅ JoernProvider initialized")
        print(f"   Joern path: {provider.joern_path}")
        return True
    except Exception as e:
        print(f"⚠️  JoernProvider unavailable: {e}")
        print("   This is expected if Joern is not installed yet")
        return False


def test_code_analyzer_hybrid():
    """Test CodeAnalyzer hybrid strategy selection."""
    print("\n" + "="*60)
    print("Test 2: CodeAnalyzer Hybrid Strategy")
    print("="*60)
    
    from knowgraph.domain.intelligence.code_analyzer import CodeAnalyzer
    
    analyzer = CodeAnalyzer()
    print(f"✅ CodeAnalyzer initialized")
    print(f"   Joern enabled: {analyzer.use_joern}")
    
    # Test 1: Small Python file (should use AST)
    python_code = "def hello(): return 'world'"
    entities = analyzer.extract_entities(python_code, "test.py")
    print(f"✅ Python extraction: {len(entities)} entities")
    
    # Test 2: Language detection
    for ext in ["test.c", "test.cpp", "test.java", "test.js"]:
        lang = analyzer._detect_language(ext)
        print(f"   {ext} → {lang}")
    
    return True


def test_edge_types():
    """Test new EdgeType enum."""
    print("\n" + "="*60)
    print("Test 3: EdgeType Extension")
    print("="*60)
    
    from knowgraph.shared.types import EdgeType
    from typing import get_args
    
    edge_types = get_args(EdgeType)
    print(f"✅ EdgeType enum has {len(edge_types)} types:")
    for et in edge_types:
        marker = "🆕" if et in ["call", "data_flow", "control_flow", "ast"] else "  "
        print(f"   {marker} {et}")
    
    return True


def test_config():
    """Test Joern configuration."""
    print("\n" + "="*60)
    print("Test 4: Configuration")
    print("="*60)
    
    from knowgraph.config import (
        JOERN_ENABLED,
        JOERN_LANGUAGE_MAP,
        JOERN_MIN_FILE_SIZE,
        JOERN_FAST_LANGUAGES,
    )
    
    print(f"✅ JOERN_ENABLED: {JOERN_ENABLED}")
    print(f"   Language support: {len(JOERN_LANGUAGE_MAP)} languages")
    print(f"   LOC threshold: {JOERN_MIN_FILE_SIZE}")
    print(f"   Fast languages: {JOERN_FAST_LANGUAGES}")
    
    return True


if __name__ == "__main__":
    print("\n🧪 KnowGraph v0.8.0 - Joern Integration Test Suite")
    
    results = []
    results.append(("JoernProvider", test_joern_provider_init()))
    results.append(("CodeAnalyzer", test_code_analyzer_hybrid()))
    results.append(("EdgeTypes", test_edge_types()))
    results.append(("Config", test_config()))
    
    print("\n" + "="*60)
    print("Test Results Summary")
    print("="*60)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(r for _, r in results)
    print("\n" + "="*60)
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("⚠️  Some tests failed (may be expected if Joern not installed)")
    print("="*60 + "\n")
