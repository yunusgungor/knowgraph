"""SHA-1 content hashing for change detection."""

import hashlib

from knowgraph.config import FILE_READ_CHUNK_SIZE


def hash_content(content: str) -> str:
    """Generate SHA-1 hash of content.

    Uses UTF-8 encoding and returns lowercase hex digest.

    Args:
    ----
        content: Text content to hash

    Returns:
    -------
        40-character SHA-1 hash (lowercase hex)

    Example:
    -------
        >>> hash_content("hello world")
        '2aae6c35c94fcfb415dbe95f408b9ce91ee846ed'

    """
    return hashlib.sha1(content.encode("utf-8")).hexdigest()  # noqa: S324


def hash_file(file_path: str) -> str:
    """Generate SHA-1 hash of file contents.

    Args:
    ----
        file_path: Path to file

    Returns:
    -------
        40-character SHA-1 hash (lowercase hex)

    Raises:
    ------
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read

    """
    hasher = hashlib.sha1()  # noqa: S324
    with open(file_path, "rb") as file:
        # Read in chunks to handle large files
        for chunk in iter(lambda: file.read(FILE_READ_CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
