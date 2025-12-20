"""SHA-1 content hashing for change detection."""

import hashlib


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
