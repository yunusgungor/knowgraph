"""AI-powered auto-tagging for conversation snippets.

Automatically suggests tags based on snippet content using:
- Entity extraction (getUserById, FastAPI, JWT)
- Similarity to existing tags
- Topic categorization
"""

import re

from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder


def extract_entities(content: str) -> list[str]:
    """Extract code entities and technical terms from content.

    Looks for:
    - Function/method names (camelCase, snake_case)
    - Class names (PascalCase)
    - Technology names (FastAPI, React, JWT)
    - File extensions (.py, .js, .md)

    Args:
    ----
        content: Snippet content

    Returns:
    -------
        List of extracted entities

    """
    entities = []

    # 1. Extract camelCase/PascalCase identifiers
    camel_pattern = r"\b[a-z][a-z0-9]*(?:[A-Z][a-z0-9]*)+\b"
    camel_matches = re.findall(camel_pattern, content)
    entities.extend(camel_matches)

    # 2. Extract snake_case identifiers
    snake_pattern = r"\b[a-z_][a-z0-9_]{2,}\b"
    snake_matches = re.findall(snake_pattern, content)
    entities.extend([m for m in snake_matches if "_" in m])

    # 3. Extract capitalized tech terms (FastAPI, React, JWT)
    tech_pattern = r"\b[A-Z][A-Za-z0-9]{2,}\b"
    tech_matches = re.findall(tech_pattern, content)
    entities.extend(tech_matches)

    # 4. Extract backtick-wrapped code
    backtick_pattern = r"`([^`]+)`"
    backtick_matches = re.findall(backtick_pattern, content)
    entities.extend(backtick_matches)

    # Deduplicate
    unique_entities = []
    seen = set()
    for entity in entities:
        entity_lower = entity.lower()
        if entity_lower not in seen and len(entity) >= 3:
            seen.add(entity_lower)
            unique_entities.append(entity)

    return unique_entities


def categorize_topic(content: str, entities: list[str]) -> str:
    """Categorize snippet into topic area.

    Categories:
    - authentication
    - database
    - api
    - ui
    - testing
    - deployment
    - config
    - documentation
    - general

    Args:
    ----
        content: Snippet content
        entities: Extracted entities

    Returns:
    -------
        Topic category

    """
    content_lower = content.lower()
    entities_lower = " ".join(entities).lower()
    combined = content_lower + " " + entities_lower

    # Keyword mapping to categories
    categories = {
        "authentication": ["auth", "login", "jwt", "oauth", "token", "password", "session"],
        "database": ["database", "sql", "query", "table", "schema", "migration", "orm"],
        "api": ["api", "endpoint", "route", "request", "response", "rest", "graphql"],
        "ui": ["component", "render", "ui", "interface", "button", "form", "react", "vue"],
        "testing": ["test", "assert", "mock", "spec", "coverage", "pytest", "jest"],
        "deployment": ["deploy", "docker", "kubernetes", "ci", "cd", "pipeline", "build"],
        "config": ["config", "settings", "environment", "env", "yaml", "json"],
        "documentation": ["readme", "doc", "documentation", "guide", "tutorial"],
    }

    # Score each category
    scores = {}
    for category, keywords in categories.items():
        score = sum(1 for keyword in keywords if keyword in combined)
        if score > 0:
            scores[category] = score

    # Return highest scoring category or 'general'
    if scores:
        return max(scores.items(), key=lambda x: x[1])[0]
    return "general"


def suggest_tags(
    content: str,
    existing_tags: list[str] | None = None,
    max_suggestions: int = 5,
) -> list[str]:
    """Suggest tags for a snippet based on content analysis.

    Args:
    ----
        content: Snippet content
        existing_tags: Previously used tags in system
        max_suggestions: Maximum number of suggestions

    Returns:
    -------
        List of suggested tags (sorted by relevance)

    """
    suggestions = []

    # 1. Extract entities as potential tags
    entities = extract_entities(content)
    suggestions.extend(entities[:3])  # Top 3 entities

    # 2. Add topic category
    topic = categorize_topic(content, entities)
    suggestions.append(f"topic:{topic}")

    # 3. Find similar existing tags using tokenization
    if existing_tags:
        embedder = SparseEmbedder()
        content_tokens = set(embedder.embed_code(content).keys())

        similar_tags = []
        for tag in existing_tags:
            tag_tokens = set(embedder.embed_code(tag).keys())
            overlap = len(content_tokens & tag_tokens)
            if overlap >= 2:  # At least 2 token overlap
                similar_tags.append((tag, overlap))

        # Add top similar tags
        similar_tags.sort(key=lambda x: x[1], reverse=True)
        suggestions.extend([tag for tag, _ in similar_tags[:2]])

    # Deduplicate and limit
    unique_suggestions = []
    seen = set()
    for suggestion in suggestions:
        if suggestion.lower() not in seen:
            seen.add(suggestion.lower())
            unique_suggestions.append(suggestion)

            if len(unique_suggestions) >= max_suggestions:
                break

    return unique_suggestions


def auto_tag_snippet(content: str, existing_tags: list[str] | None = None) -> dict:
    """Comprehensive auto-tagging of a snippet.

    Args:
    ----
        content: Snippet content
        existing_tags: Previously used tags

    Returns:
    -------
        Dictionary with:
        - suggested_tags: List of tag suggestions
        - entities: Extracted entities
        - topic: Topic category
        - confidence: Confidence score (0-1)

    """
    entities = extract_entities(content)
    topic = categorize_topic(content, entities)
    suggestions = suggest_tags(content, existing_tags)

    # Calculate confidence based on entity extraction quality
    confidence = min(1.0, len(entities) / 5.0)  # More entities = higher confidence

    return {
        "suggested_tags": suggestions,
        "entities": entities,
        "topic": topic,
        "confidence": confidence,
    }


# Example usage
if __name__ == "__main__":
    sample = """
    I implemented JWT authentication using FastAPI.
    The authenticateUser function validates tokens and returns user data.
    Used the PyJWT library for token encoding/decoding.
    """

    result = auto_tag_snippet(sample)
    print(f"Suggested tags: {result['suggested_tags']}")
    print(f"Entities: {result['entities']}")
    print(f"Topic: {result['topic']}")
    print(f"Confidence: {result['confidence']:.2f}")
