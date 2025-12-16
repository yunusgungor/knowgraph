from knowgraph.domain.intelligence.code_analyzer import ASTAnalyzer

CODE_SAMPLE = """
import os

class MyClass:
    def __init__(self):
        self.x = 1

    def method_one(self):
        '''Docstring'''
        return True

def my_function(a, b):
    return a + b
"""


def test_analyze_python_code():
    analyzer = ASTAnalyzer()
    entities = analyzer.extract_entities(CODE_SAMPLE)

    assert len(entities) == 4

    # Check Class
    classes = [e for e in entities if e.type == "class"]
    assert len(classes) == 1
    assert classes[0].name == "MyClass"

    # Check Methods/Functions
    funcs = [e for e in entities if e.type == "function"]
    assert len(funcs) == 3
    names = {f.name for f in funcs}
    assert "method_one" in names
    assert "my_function" in names


def test_analyze_invalid_code():
    analyzer = ASTAnalyzer()
    # Should not crash on syntax error
    entities = analyzer.extract_entities("def broken_code(: return")
    assert entities == []


def test_analyze_empty():
    analyzer = ASTAnalyzer()
    assert analyzer.extract_entities("") == []
