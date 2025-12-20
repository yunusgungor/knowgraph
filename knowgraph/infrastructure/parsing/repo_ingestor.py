"""Repository ingestor for converting Git repositories to markdown.

Uses gitingest to clone and convert repositories to markdown format.
"""

import tempfile
from pathlib import Path
from typing import Literal

from knowgraph.shared.memory_profiler import memory_guard
from knowgraph.shared.tracing import trace_operation

try:
    from gitingest import ingest

    GITINGEST_AVAILABLE = True
except ImportError:
    ingest = None
    GITINGEST_AVAILABLE = False

try:
    from gitingest import ingest_async
except ImportError:
    ingest_async = None


class RepositoryIngestorError(Exception):
    """Base exception for repository ingestor errors."""


class GitingestNotInstalledError(RepositoryIngestorError):
    """Raised when gitingest is not installed."""


SourceType = Literal["repository", "directory", "markdown", "conversation"]


def detect_source_type(input_path: str) -> SourceType:
    """Detect whether input is a repository URL, local directory, markdown file, or conversation.

    Args:
    ----
        input_path: Path or URL to analyze

    Returns:
    -------
        Source type: "repository", "directory", "markdown", or "conversation"

    """
    path_lower = input_path.lower()

    # Check if it's a Git repository URL
    if any(host in path_lower for host in ["github.com", "gitlab.com", "bitbucket.org"]):
        return "repository"

    # Local path
    path_obj = Path(input_path)
    if path_obj.exists():
        if path_obj.is_file():
            # Check for conversation files
            if path_obj.suffix == ".aichat":
                return "conversation"
            if path_obj.suffix == ".txt" and "antigravity" in str(path_obj):
                return "conversation"

            # For JSON files, check content to determine if it's a conversation
            if path_obj.suffix == ".json":
                try:
                    import json

                    with open(path_obj, encoding="utf-8") as f:
                        data = json.load(f)

                    # Check for conversation indicators
                    if any(
                        key in data for key in ["messages", "entries", "chat_messages", "sessionId"]
                    ):
                        return "conversation"
                    if "conversation" in path_obj.name.lower() or "chat" in path_obj.name.lower():
                        return "conversation"
                except (json.JSONDecodeError, OSError):
                    pass

            return "markdown" if path_obj.suffix == ".md" else "directory"
        # Directory - check if it contains only markdown files
        if path_obj.is_dir():
            md_files = list(path_obj.glob("**/*.md"))
            other_files = [f for f in path_obj.glob("**/*") if f.is_file() and f.suffix != ".md"]
            # If directory has markdown files and no other files, it's a markdown directory
            if md_files and not other_files:
                return "markdown"
        return "directory"

    # Default to directory for local paths
    if not any(proto in path_lower for proto in ["http://", "https://", "git@"]):
        return "directory"

    # Default to repository for URLs
    return "repository"


async def ingest_repository(
    repo_url_or_path: str,
    output_path: Path | None = None,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    max_file_size: int | None = None,
    access_token: str | None = None,
) -> tuple[str, Path]:
    """Ingest a Git repository or code directory into markdown format.

    Args:
    ----
        repo_url_or_path: Git repository URL or local directory path
        output_path: Path to save the markdown digest (if None, uses temp file)
        include_patterns: File patterns to include (e.g., ["*.py", "*.md"])
        exclude_patterns: File patterns to exclude (e.g., ["node_modules/*"])
        max_file_size: Maximum file size in bytes
        access_token: GitHub Personal Access Token for private repositories

    Returns:
    -------
        Tuple of (markdown_content, output_file_path)

    Raises:
    ------
        GitingestNotInstalledError: If gitingest is not installed
        RepositoryIngestorError: If ingestion fails

    """
    with memory_guard(
        operation_name=f"ingest_repo[{repo_url_or_path[:50]}]",
        warning_threshold_mb=150,
        critical_threshold_mb=400,
    ):
        with trace_operation(
            "repo_ingestor.ingest_repository",
            source=repo_url_or_path,
        ):
            if ingest_async is None:
                msg = "gitingest is not installed. Install it with: pip install gitingest>=0.3.1"
                raise GitingestNotInstalledError(msg)

            try:
                # Call gitingest async with parameters directly
                # Build kwargs only with non-None values
                kwargs = {}
                if include_patterns is not None:
                    kwargs["include_patterns"] = include_patterns
                if exclude_patterns is not None:
                    kwargs["exclude_patterns"] = exclude_patterns
                if max_file_size is not None:
                    kwargs["max_file_size"] = max_file_size
                if access_token is not None:
                    kwargs["token"] = access_token

                summary, tree, content = await ingest_async(repo_url_or_path, **kwargs)

                # Build complete markdown document
                markdown_content = f"""# Repository Digest

{summary}

## Directory Structure

```
{tree}
```

## File Contents

{content}
"""

                # Save to file
                if output_path is None:
                    # Create temporary file
                    with tempfile.NamedTemporaryFile(  # noqa: SIM115
                        mode="w",
                        suffix=".md",
                        prefix="repo_digest_",
                        delete=False,
                        encoding="utf-8",
                    ) as temp_file:
                        output_path = Path(temp_file.name)
                        temp_file.write(markdown_content)
                else:
                    output_path = Path(output_path)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(markdown_content)

                return markdown_content, output_path

            except Exception as e:
                msg = f"Failed to ingest repository: {e}"
                raise RepositoryIngestorError(msg) from e


async def ingest_source(
    input_path: str,
    output_path: Path | None = None,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    max_file_size: int | None = None,
    access_token: str | None = None,
    force_type: SourceType | None = None,
) -> tuple[str, Path, SourceType]:
    """Intelligently ingest any source (repository, directory, or markdown).

    Automatically detects the source type and processes accordingly.

    Args:
    ----
        input_path: Path or URL to the source
        output_path: Path to save processed markdown
        include_patterns: File patterns to include
        exclude_patterns: File patterns to exclude
        max_file_size: Maximum file size in bytes
        access_token: GitHub Personal Access Token
        force_type: Force specific source type detection

    Returns:
    -------
        Tuple of (markdown_content, output_path, source_type)

    Raises:
    ------
        RepositoryIngestorError: If ingestion fails

    """
    # Detect source type
    source_type = force_type if force_type else detect_source_type(input_path)

    if source_type == "markdown":
        # Already markdown, just read and return
        path_obj = Path(input_path)
        with open(path_obj, encoding="utf-8") as f:
            content = f.read()
        return content, path_obj, source_type

    # For repositories and directories, use gitingest
    content, out_path = await ingest_repository(
        repo_url_or_path=input_path,
        output_path=output_path,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        max_file_size=max_file_size,
        access_token=access_token,
    )

    return content, out_path, source_type
