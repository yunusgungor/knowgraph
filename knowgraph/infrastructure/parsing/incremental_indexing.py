"""Incremental indexing support for conversations.

Tracks last indexed timestamp to only process new/updated conversations.
"""

import json
from datetime import datetime
from pathlib import Path


class IndexingCheckpoint:
    """Manages indexing checkpoint data."""

    def __init__(self, checkpoint_file: Path):
        """Initialize checkpoint manager.

        Args:
        ----
            checkpoint_file: Path to checkpoint JSON file

        """
        self.checkpoint_file = checkpoint_file
        self.data = self._load()

    def _load(self) -> dict:
        """Load checkpoint data from file."""
        if self.checkpoint_file.exists():
            try:
                return json.loads(self.checkpoint_file.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def save(self) -> None:
        """Save checkpoint data to file."""
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file.write_text(json.dumps(self.data, indent=2))

    def get_last_indexed(self, file_path: str) -> datetime | None:
        """Get last indexed timestamp for a file.

        Args:
        ----
            file_path: File path (as string for JSON serialization)

        Returns:
        -------
            Last indexed timestamp or None

        """
        timestamp_str = self.data.get(file_path)
        if timestamp_str:
            try:
                return datetime.fromisoformat(timestamp_str)
            except (ValueError, TypeError):
                return None
        return None

    def set_last_indexed(self, file_path: str, timestamp: datetime) -> None:
        """Set last indexed timestamp for a file.

        Args:
        ----
            file_path: File path
            timestamp: Indexed timestamp

        """
        self.data[file_path] = timestamp.isoformat()

    def clear(self) -> None:
        """Clear all checkpoint data."""
        self.data = {}
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()


def should_index_file(
    file_path: Path,
    checkpoint: IndexingCheckpoint,
) -> bool:
    """Check if file should be indexed based on modification time.

    Args:
    ----
        file_path: File to check
        checkpoint: Indexing checkpoint

    Returns:
    -------
        True if file should be indexed

    """
    file_str = str(file_path)
    last_indexed = checkpoint.get_last_indexed(file_str)

    if last_indexed is None:
        # Never indexed before
        return True

    # Check file modification time
    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

    # Index if modified after last indexing
    return file_mtime > last_indexed


async def incremental_ingest_directory(
    conversations_dir: Path,
    output_dir: Path,
    checkpoint_file: Path | None = None,
) -> tuple[list[tuple[str, Path]], dict]:
    """Incrementally ingest conversations (only new/updated files).

    Args:
    ----
        conversations_dir: Directory with conversation files
        output_dir: Output directory for markdown
        checkpoint_file: Checkpoint file path (default: output_dir/.checkpoint)

    Returns:
    -------
        Tuple of (results, stats)
        - results: List of (markdown, path) tuples
        - stats: Dictionary with indexing statistics

    """
    from knowgraph.infrastructure.parsing.conversation_ingestor import ingest_conversation

    # Initialize checkpoint
    if checkpoint_file is None:
        checkpoint_file = output_dir / ".indexing_checkpoint.json"

    checkpoint = IndexingCheckpoint(checkpoint_file)

    # Scan for conversation files
    patterns = ["*.aichat", "*.json", "*.txt", "*.md"]
    all_files = []
    for pattern in patterns:
        all_files.extend(conversations_dir.glob(f"**/{pattern}"))

    # Filter to files that need indexing
    to_index = [f for f in all_files if should_index_file(f, checkpoint)]

    # Index files
    results = []
    indexed_count = 0
    skipped_count = len(all_files) - len(to_index)
    error_count = 0

    for conv_file in to_index:
        try:
            # Determine output path
            rel_path = conv_file.relative_to(conversations_dir)
            out_path = output_dir / rel_path.with_suffix(".md")

            # Ingest conversation
            content, path = await ingest_conversation(conv_file, out_path)
            results.append((content, path))

            # Update checkpoint
            checkpoint.set_last_indexed(str(conv_file), datetime.now())
            indexed_count += 1

        except Exception:
            error_count += 1
            continue

    # Save checkpoint
    checkpoint.save()

    stats = {
        "total_files": len(all_files),
        "indexed": indexed_count,
        "skipped": skipped_count,
        "errors": error_count,
        "checkpoint_file": str(checkpoint_file),
    }

    return results, stats


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test():
        results, stats = await incremental_ingest_directory(
            Path("./conversations"),
            Path("./output"),
        )
        print(f"Indexed: {stats['indexed']}, Skipped: {stats['skipped']}")

    asyncio.run(test())
