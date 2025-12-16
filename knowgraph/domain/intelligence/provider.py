"""Intelligence Provider Interface."""

from abc import ABC, abstractmethod
from typing import NamedTuple


class Entity(NamedTuple):
    """Extracted entity from text."""

    name: str
    type: str
    description: str


class Relationship(NamedTuple):
    """Extracted relationship between entities."""

    source: str
    target: str
    description: str


class IntelligenceProvider(ABC):
    """Abstract base class for intelligence providers."""

    @abstractmethod
    async def generate_text(self, prompt: str) -> str:
        """Generate text from a prompt."""
        ...

    @abstractmethod
    async def extract_entities(self, text: str) -> list[Entity]:
        """Extract entities from text."""
        ...

    @abstractmethod
    async def extract_entities_batch(self, texts: list[str]) -> list[list[Entity]]:
        """Extract entities from multiple texts in a batch."""
        ...

    @abstractmethod
    async def extract_relationships(self, text: str, entities: list[Entity]) -> list[Relationship]:
        """Extract relationships from text given a list of known entities."""
        ...
