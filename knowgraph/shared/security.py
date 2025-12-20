"""Security utilities for path validation and input sanitization."""

import os
from pathlib import Path
from typing import Any


def validate_path(
    path: str | Path,
    must_exist: bool = False,
    must_be_file: bool = False,
    allowed_parent: Path | None = None,
) -> Path:
    """Validate and sanitize file system path.

    Prevents directory traversal attacks and validates path constraints.

    Args:
    ----
        path: Path to validate
        must_exist: Require path to exist
        must_be_file: Require path to be a file (not directory)
        allowed_parent: Optional parent directory to restrict paths to (security boundary)

    Returns:
    -------
        Validated Path object

    Raises:
    ------
        ValueError: If path validation fails
        FileNotFoundError: If must_exist=True and path doesn't exist

    """
    try:
        # Convert to Path object and resolve (follows symlinks, normalizes)
        validated_path = Path(path).resolve()

        # Security: Check if resolved path escapes allowed boundary
        if allowed_parent:
            allowed_parent_resolved = Path(allowed_parent).resolve()
            try:
                # Check if validated_path is within allowed_parent
                validated_path.relative_to(allowed_parent_resolved)
            except ValueError:
                raise ValueError(
                    f"Path escapes allowed directory: {validated_path} is not under {allowed_parent_resolved}"
                )

        # Validate existence if required
        if must_exist and not validated_path.exists():
            raise FileNotFoundError(f"Path does not exist: {validated_path}")

        # Validate file type if required
        if must_be_file and must_exist and not validated_path.is_file():
            raise ValueError(f"Path is not a file: {validated_path}")

        return validated_path

    except (ValueError, FileNotFoundError):
        raise
    except Exception as error:
        raise ValueError(f"Invalid path: {path}") from error


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """Sanitize filename to prevent injection attacks.

    Args:
    ----
        filename: Filename to sanitize
        max_length: Maximum filename length

    Returns:
    -------
        Sanitized filename

    Raises:
    ------
        ValueError: If filename is invalid or empty after sanitization

    """
    # Remove null bytes
    sanitized = filename.replace("\0", "")

    # Remove or replace dangerous characters
    dangerous_chars = ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, "_")

    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip(". \t\n\r")

    # Enforce length limit
    if len(sanitized) > max_length:
        name, ext = os.path.splitext(sanitized)
        name = name[: max_length - len(ext) - 1]
        sanitized = f"{name}{ext}"

    # Validate not empty
    if not sanitized:
        raise ValueError("Filename is empty after sanitization")

    # Check for reserved names (Windows)
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
    if sanitized.upper() in reserved_names:
        sanitized = f"_{sanitized}"

    return sanitized


def validate_graph_store_path(graph_store_path: Path) -> None:
    """Validate graph store directory structure and permissions.

    Args:
    ----
        graph_store_path: Root graph storage directory

    Raises:
    ------
        ValueError: If validation fails
        PermissionError: If insufficient permissions

    """
    try:
        # Validate path exists and is a directory
        if not graph_store_path.exists():
            raise ValueError(f"Graph store does not exist: {graph_store_path}")

        if not graph_store_path.is_dir():
            raise ValueError(f"Graph store path is not a directory: {graph_store_path}")

        # Check read permission
        if not os.access(graph_store_path, os.R_OK):
            raise PermissionError(f"No read permission for graph store: {graph_store_path}")

        # Check write permission
        if not os.access(graph_store_path, os.W_OK):
            raise PermissionError(f"No write permission for graph store: {graph_store_path}")

        # Validate expected subdirectories
        required_dirs = ["nodes", "edges", "embeddings", "metadata", "index"]
        for subdir in required_dirs:
            subdir_path = graph_store_path / subdir
            if subdir_path.exists() and not subdir_path.is_dir():
                raise ValueError(f"Expected directory but found file: {subdir_path}")

    except (ValueError, PermissionError):
        raise
    except Exception as error:
        raise ValueError(f"Graph store validation failed: {error}") from error


def sanitize_query_input(query: str, max_length: int = 10000) -> str:
    """Sanitize user query input to prevent injection attacks.

    Args:
    ----
        query: Query text from user
        max_length: Maximum query length

    Returns:
    -------
        Sanitized query

    Raises:
    ------
        ValueError: If query is invalid

    """
    # Remove null bytes
    sanitized = query.replace("\0", "")

    # Strip excessive whitespace
    sanitized = " ".join(sanitized.split())

    # Enforce length limit
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    # Validate not empty
    if not sanitized.strip():
        raise ValueError("Query is empty after sanitization")

    return sanitized


def validate_json_size(json_data: dict[str, Any], max_size_bytes: int = 10 * 1024 * 1024) -> None:
    """Validate JSON data size to prevent memory exhaustion.

    Args:
    ----
        json_data: JSON data to validate
        max_size_bytes: Maximum size in bytes (default: 10MB)

    Raises:
    ------
        ValueError: If JSON exceeds size limit

    """
    import json

    json_str = json.dumps(json_data)
    size_bytes = len(json_str.encode("utf-8"))

    if size_bytes > max_size_bytes:
        raise ValueError(
            f"JSON data exceeds size limit: {size_bytes / 1024 / 1024:.2f}MB > {max_size_bytes / 1024 / 1024:.2f}MB"
        )
