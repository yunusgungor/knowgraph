"""Query classification for routing to appropriate analyzers.

This module classifies user queries as CODE, TEXT, or HYBRID to enable
intelligent routing to Joern code analysis or semantic text search.
"""

import re
from enum import Enum


class QueryType(Enum):
    """Types of queries."""
    CODE = "code"
    TEXT = "text"
    HYBRID = "hybrid"
    DATAFLOW = "dataflow"


class QueryClassifier:
    """Classify queries to determine appropriate analysis method."""

    # Code-related keywords (English + Turkish)
    CODE_KEYWORDS = {
        # General code terms
        "function", "method", "class", "code", "implementation",
        "algorithm", "logic", "file", "module",

        # Security & vulnerabilities
        "vulnerability", "vulnerabilities", "security", "secure",
        "bug", "error", "issue", "flaw", "exploit",
        "sql injection", "xss", "cross-site", "buffer overflow",
        "injection", "sanitize", "validate",

        # Code quality
        "dead code", "unused", "unreachable", "deprecated",
        "complexity", "refactor", "optimize",

        # Code structure
        "call graph", "dependency", "dependencies", "import",
        "recursive", "recursion", "loop", "iteration",

        # Turkish equivalents
        "fonksiyon", "metot", "sınıf", "kod", "uygulama",
        "güvenlik", "güvenli", "açık", "hata", "sorun",
        "kullanılmayan", "karmaşıklık", "bağımlılık",
    }

    # Dataflow keywords
    DATAFLOW_KEYWORDS = {
        "data flow", "dataflow", "taint", "taint analysis",
        "flow", "trace", "path", "source", "sink",
        "veri akışı", "akış", "izle", "yol", "kaynak", "hedef",
        "flows to", "leads to", "reaches", "ulaşır", "gider"
    }

    # Code-related patterns (regex)
    CODE_PATTERNS = [
        r"\bfind\s+(sql|xss|buffer|injection|vulnerability)",
        r"\bshow\s+me\s+(function|method|class|code)",
        r"\bis\s+\w+\s+(secure|safe|vulnerable)",
        r"\b(analyze|check|scan)\s+(code|security)",
        r"\w+\s+(açığı|güvenli)\s+mi",  # Turkish patterns
    ]

    # Dataflow patterns (Source -> Sink)
    DATAFLOW_PATTERNS = [
        r"(flow|trace|path)\s+(from|between)\s+(?P<source>.+?)\s+(to|and)\s+(?P<sink>.+)",
        r"how\s+(does|do)\s+(?P<source>.+?)\s+(flow|reach|affect)\s+(?P<sink>.+)",
        r"(?P<source>.+?)\s+(flows?|leads?)\s+to\s+(?P<sink>.+)",
        r"(show|find)\s+data\s*flow\s+from\s+(?P<source>.+?)\s+to\s+(?P<sink>.+)",
        r"(?P<source>.+?)\s+(ile|ve)\s+(?P<sink>.+?)\s+(arasındaki|arasında)\s+(akış|yol)",  # Turkish
        r"(?P<source>.+?)\s+(kaynağından|den)\s+(?P<sink>.+?)\s+(hedefine|e)\s+(veri\s+akışı|akış)", # Turkish
    ]

    # Question patterns that suggest code analysis
    CODE_QUESTION_PATTERNS = [
        r"(is|are)\s+\w+\s+(secure|safe|vulnerable)",
        r"(does|do)\s+\w+\s+(have|contain)\s+(bug|vulnerability)",
        r"(what|which)\s+(function|method|class)",
        r"\w+\s+güvenli\s+mi",  # Turkish: "is X secure?"
    ]

    def classify(self, query: str) -> QueryType:
        """Classify a query as CODE, TEXT, or HYBRID.

        Args:
            query: User's natural language query

        Returns:
            QueryType indicating classification
        """
        query_lower = query.lower()

        # Check for Dataflow patterns FIRST (most specific)
        for pattern in self.DATAFLOW_PATTERNS:
            if re.search(pattern, query_lower):
                return QueryType.DATAFLOW

        # Strong CODE indicators - always CODE
        strong_code_indicators = [
            "vulnerability", "vulnerabilities", "sql injection", "xss",
            "buffer overflow", "injection", "exploit",
            "dead code", "unused code", "unreachable",
            "call graph", "recursive", "recursion", "scan for", "find bug",
            "güvenlik açık", "açık var", "zafiyet",
            "who calls", "callers of", "usage of", "references to",
            "chain", "calls between",
            "complexity", "cyclomatic", "ast", "syntax tree",
            "subclasses", "superclasses", "inherits", "extends",
            "cfg", "pdg", "cdg", "control flow", "dependence",
            "slice", "slicing", "usage", "variable", "identifier",
            "slice", "slicing", "usage", "variable", "identifier",
            "literal", "hardcoded", "string", "constant",
            "annotation", "decorator", "import", "dependency", "loop", "if statement"
        ]

        for indicator in strong_code_indicators:
            if indicator in query_lower:
                return QueryType.CODE

        # Action words + code terms = CODE
        action_words = ["find", "show", "list", "get", "scan", "check", "analyze", "detect"]
        code_terms = ["function", "method", "class", "code", "implementation",
                     "fonksiyon", "metot", "kod"]

        has_action = any(word in query_lower for word in action_words)
        has_code_term = any(term in query_lower for term in code_terms)

        if has_action and has_code_term:
            return QueryType.CODE

        # Security questions about code = HYBRID (want docs + analysis)
        security_terms = ["secure", "safe", "güvenli", "security", "güvenlik", "vulnerable"]
        has_security = any(term in query_lower for term in security_terms)

        # "is X secure?" or "is X safe?" where X is code-related = HYBRID
        code_indicators = ["function", "method", "class", "code", "implementation",
                          "fonksiyon", "metot", "sınıf", "kod", "login", "auth"]
        has_code_indicator = any(indicator in query_lower for indicator in code_indicators)

        if has_security and (has_code_indicator or "code" in query_lower or "kod" in query_lower):
            return QueryType.HYBRID

        # Questions about implementation/how code works = HYBRID
        explanation_words = ["how", "why", "explain", "describe", "nasıl", "neden", "açıkla"]
        has_explanation = any(word in query_lower for word in explanation_words)

        if has_explanation and has_code_term:
            return QueryType.HYBRID

        # Questions about security in general = HYBRID (might want both)
        if has_security and has_explanation:
            return QueryType.HYBRID

        # Default to TEXT for everything else
        return QueryType.TEXT

    def is_code_query(self, query: str) -> bool:
        """Quick check if query is code-related (CODE or HYBRID).

        Args:
            query: User's query

        Returns:
            True if query involves code analysis
        """
        query_type = self.classify(query)
        return query_type in (QueryType.CODE, QueryType.HYBRID)

    def get_code_confidence(self, query: str) -> float:
        """Get confidence score for code classification.

        Args:
            query: User's query

        Returns:
            Float between 0.0 and 1.0 indicating confidence
        """
        query_lower = query.lower()

        score = 0
        max_score = 10

        # Keyword matches (up to 5 points)
        keyword_matches = sum(1 for kw in self.CODE_KEYWORDS if kw in query_lower)
        score += min(keyword_matches, 5)

        # Pattern matches (up to 3 points)
        pattern_matches = sum(1 for p in self.CODE_PATTERNS if re.search(p, query_lower))
        score += min(pattern_matches * 1.5, 3)

        # Question pattern matches (up to 2 points)
        question_matches = sum(1 for p in self.CODE_QUESTION_PATTERNS if re.search(p, query_lower))
        score += min(question_matches, 2)

        return min(score / max_score, 1.0)
