"""Prompts for intelligence tasks."""

ENTITY_EXTRACTION_PROMPT = """
Analyze the following code snippet and extract key entities such as Classes, Functions, Modules, Global Variables, and important Concepts.
Return the result as a JSON list of objects, where each object has:
- "name": The name of the entity
- "type": The type (Class, Function, etc.)
- "description": A brief description of what it does responsibilities.

Code:
{text}

Output JSON:
"""

RELATIONSHIP_EXTRACTION_PROMPT = """
Analyze the following code snippet and the provided list of entities. Identify relationships between them (e.g., inherits from, calls, imports, instantiates).
Return the result as a JSON list of objects, where each object has:
- "source": Name of the source entity
- "target": Name of the target entity
- "description": Description of the relationship

Entities:
{entities}

Code:
{text}

Output JSON:
"""
