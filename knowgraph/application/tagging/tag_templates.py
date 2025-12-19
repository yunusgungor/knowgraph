"""Tag templates for standardized tagging.

Provides pre-defined tag templates for common patterns:
- Code patterns (design patterns, refactoring patterns)
- Technologies (frameworks, libraries, languages)
- Topics (domains, activities, phases)
"""

from dataclasses import dataclass
from enum import Enum


class TagCategory(Enum):
    """Tag categories."""

    PATTERN = "pattern"
    TECHNOLOGY = "tech"
    TOPIC = "topic"
    ACTIVITY = "activity"
    PHASE = "phase"


@dataclass
class TagTemplate:
    """A tag template."""

    category: TagCategory
    name: str
    aliases: list[str]
    description: str


# Pre-defined templates
TAG_TEMPLATES = [
    # Design Patterns
    TagTemplate(
        category=TagCategory.PATTERN,
        name="design_pattern:singleton",
        aliases=["singleton", "single instance"],
        description="Singleton design pattern",
    ),
    TagTemplate(
        category=TagCategory.PATTERN,
        name="design_pattern:factory",
        aliases=["factory", "factory method"],
        description="Factory design pattern",
    ),
    TagTemplate(
        category=TagCategory.PATTERN,
        name="design_pattern:observer",
        aliases=["observer", "pub-sub", "event-driven"],
        description="Observer/pub-sub pattern",
    ),
    # Technologies
    TagTemplate(
        category=TagCategory.TECHNOLOGY,
        name="tech:fastapi",
        aliases=["fastapi", "fast api"],
        description="FastAPI framework",
    ),
    TagTemplate(
        category=TagCategory.TECHNOLOGY,
        name="tech:react",
        aliases=["react", "reactjs"],
        description="React framework",
    ),
    TagTemplate(
        category=TagCategory.TECHNOLOGY,
        name="tech:jwt",
        aliases=["jwt", "json web token"],
        description="JWT authentication",
    ),
    TagTemplate(
        category=TagCategory.TECHNOLOGY,
        name="tech:docker",
        aliases=["docker", "containerization"],
        description="Docker containerization",
    ),
    # Topics
    TagTemplate(
        category=TagCategory.TOPIC,
        name="topic:authentication",
        aliases=["auth", "authentication", "login"],
        description="Authentication and authorization",
    ),
    TagTemplate(
        category=TagCategory.TOPIC,
        name="topic:database",
        aliases=["database", "db", "sql", "orm"],
        description="Database operations",
    ),
    TagTemplate(
        category=TagCategory.TOPIC,
        name="topic:api",
        aliases=["api", "endpoint", "rest"],
        description="API design and implementation",
    ),
    TagTemplate(
        category=TagCategory.TOPIC,
        name="topic:testing",
        aliases=["testing", "test", "unit test"],
        description="Testing and quality assurance",
    ),
    # Activities
    TagTemplate(
        category=TagCategory.ACTIVITY,
        name="activity:debugging",
        aliases=["debug", "debugging", "troubleshooting"],
        description="Debugging and troubleshooting",
    ),
    TagTemplate(
        category=TagCategory.ACTIVITY,
        name="activity:refactoring",
        aliases=["refactor", "refactoring", "cleanup"],
        description="Code refactoring",
    ),
    # Phases
    TagTemplate(
        category=TagCategory.PHASE,
        name="phase:design",
        aliases=["design", "planning", "architecture"],
        description="Design and planning phase",
    ),
    TagTemplate(
        category=TagCategory.PHASE,
        name="phase:implementation",
        aliases=["implementation", "coding", "development"],
        description="Implementation phase",
    ),
]


def match_template(text: str) -> list[TagTemplate]:
    """Match text to tag templates.

    Args:
    ----
        text: Text to match (tag, snippet content, etc.)

    Returns:
    -------
        List of matching templates

    """
    text_lower = text.lower()
    matches = []

    for template in TAG_TEMPLATES:
        # Check if any alias appears in text
        for alias in template.aliases:
            if alias.lower() in text_lower:
                matches.append(template)
                break

    return matches


def suggest_template_tags(content: str) -> list[str]:
    """Suggest template-based tags for content.

    Args:
    ----
        content: Content to analyze

    Returns:
    -------
        List of suggested template tag names

    """
    templates = match_template(content)
    return [t.name for t in templates]


def get_templates_by_category(category: TagCategory) -> list[TagTemplate]:
    """Get all templates in a category.

    Args:
    ----
        category: Tag category

    Returns:
    -------
        List of templates

    """
    return [t for t in TAG_TEMPLATES if t.category == category]


# Example usage
if __name__ == "__main__":
    sample = "I used FastAPI for authentication with JWT tokens"

    templates = match_template(sample)
    print(f"Matched templates: {[t.name for t in templates]}")

    suggestions = suggest_template_tags(sample)
    print(f"Suggested tags: {suggestions}")
