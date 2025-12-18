"""Common type aliases for KnowGraph.

Provides reusable type definitions for better type checking and IDE support.
"""

from pathlib import Path
from typing import Any, TypeAlias, TypeVar

# Generic type variables
T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")

# Path types
PathLike: TypeAlias = str | Path

# Data structure types
JsonDict: TypeAlias = dict[str, Any]
JsonList: TypeAlias = list[Any]
JsonValue: TypeAlias = str | int | float | bool | None | JsonDict | JsonList

# Metadata and attributes
Metadata: TypeAlias = dict[str, JsonValue]
Attributes: TypeAlias = dict[str, Any]

# Node and edge identifiers
NodeId: TypeAlias = str
EdgeId: TypeAlias = str
GraphPath: TypeAlias = str

# Score and weight types
Score: TypeAlias = float
Weight: TypeAlias = float
Confidence: TypeAlias = float

# Content types
Content: TypeAlias = str
Hash: TypeAlias = str

# Query types
QueryString: TypeAlias = str
QueryResults: TypeAlias = list[Any]

# Time types
Timestamp: TypeAlias = float
TTL: TypeAlias = int | float

# Cache types
CacheKey: TypeAlias = str
CacheValue: TypeAlias = Any

# Function signature types
ValidatorFunc: TypeAlias = Any  # Callable[[Any, str], Any]
DecoratorFunc: TypeAlias = Any  # Callable[[Callable], Callable]
