"""CLI command for indexing markdown files, repositories, and code directories into knowledge graph."""

import asyncio
import glob
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import click

from knowgraph.application.indexing.graph_builder import (
    create_nodes_from_chunks,
    normalize_markdown_content,
    SmartGraphBuilder,
)
from knowgraph.config import (
    DEFAULT_GRAPH_STORE_PATH,
    EDGES_FILENAME,
)

LANGUAGE_MAP = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "jsx": "javascript",
    "tsx": "typescript",
    "rs": "rust",
    "rb": "ruby",
    "md": "markdown",
    "java": "java",
    "go": "go",
    "php": "php",
    "html": "html",
    "css": "css",
    "txt": "text",
    "sql": "sql",
    "json": "json",
    "yml": "yaml",
    "yaml": "yaml",
    "xml": "xml",
    "csv": "csv",
    "tsv": "tsv",
    "ini": "ini",
    "conf": "conf",
    "cfg": "cfg",
    "properties": "properties",
    "toml": "toml",
    "cpp": "cpp",
    "cxx": "cpp",
    "cc": "cpp",
    "c": "c",
    "h": "c",
    "hpp": "cpp",
    "cs": "csharp",
    "kt": "kotlin",
    "swift": "swift",
    "m": "objectivec",
    "dart": "dart",
    "scala": "scala",
    "erl": "erlang",
    "ex": "elixir",
    "lua": "lua",
    "sh": "shell",
    "bash": "shell",
}

# Derived maps for easier access
EXT_MAP = {f".{ext}": lang for ext, lang in LANGUAGE_MAP.items()}
CODE_PATTERNS = [f"**/*.{ext}" for ext in LANGUAGE_MAP.keys()]


from knowgraph.domain.intelligence.provider import IntelligenceProvider
from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder
from knowgraph.infrastructure.intelligence.openai_provider import OpenAIProvider
from knowgraph.infrastructure.parsing.chunker import chunk_markdown
from knowgraph.infrastructure.parsing.hasher import hash_content
from knowgraph.infrastructure.parsing.repo_ingestor import (
    RepositoryIngestorError,
    detect_source_type,
    ingest_source,
)
from knowgraph.infrastructure.search.sparse_index import SparseIndex
from knowgraph.infrastructure.storage.filesystem import write_all_edges, write_node_json
from knowgraph.infrastructure.storage.manifest import Manifest, write_manifest, read_manifest
from knowgraph.shared.security import validate_path


async def run_index(
    input_path: str,
    output_path: str,
    verbose: bool = False,
    provider: IntelligenceProvider | None = None,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    access_token: str | None = None,
    link_conversations: bool = False,
    incremental: bool = False,
) -> None:
    """Execute indexing process (AI-Driven).

    Supports markdown files, directories, Git repositories, and code directories.

    Args:
    ----
        input_path: Path to input (markdown, code, or repo URL)
        output_path: Path for graph storage
        verbose: Enable verbose logging
        provider: Intelligence provider (defaults to OpenAI)
        include_patterns: File patterns to include
        exclude_patterns: File patterns to exclude
        access_token: GitHub token for private repos
        link_conversations: Auto-discover and link conversations
        incremental: Only index new/modified files

    """
    start_time = time.time()

    # Detect source type
    source_type = detect_source_type(input_path)

    if verbose:
        click.echo(f"Detected source type: {source_type}")
        click.echo(f"Indexing {input_path} (AI Mode)...")

    # Step 1: Process source based on type
    temp_files_to_cleanup = []

    try:
        if source_type == "repository" or (
            source_type == "directory" and not Path(input_path).exists()
        ):
            # It's a repository URL or remote directory - use git clone/zip
            if verbose:
                click.echo("Remote repository detected...")

            # Create unique temp dir
            temp_dir = tempfile.mkdtemp(prefix="knowgraph_repo_")
            temp_path = Path(temp_dir)
            temp_files_to_cleanup.append(temp_path)

            # Check for git
            if shutil.which("git") is not None:
                # Use git clone if available
                if verbose:
                    click.echo("Cloning repository (git)...")

                subprocess.run(
                    ["git", "clone", "--depth", "1", input_path, str(temp_path)],
                    check=True,
                    capture_output=True,
                )
            else:
                # Fallback to ZIP download
                if verbose:
                    click.echo("Git not found. Attempting ZIP download...")

                import urllib.request
                import zipfile
                import io

                # Heuristic for GitHub URLs
                # https://github.com/user/repo -> https://github.com/user/repo/archive/refs/heads/main.zip
                normalized_url = input_path.rstrip("/")
                if normalized_url.endswith(".git"):
                    normalized_url = normalized_url[:-4]

                # Try 'main', then 'master'
                branches = ["main", "master"]
                downloaded = False

                for branch in branches:
                    zip_url = f"{normalized_url}/archive/refs/heads/{branch}.zip"
                    try:
                        if verbose:
                            click.echo(f"  Trying {branch} branch...")

                        with urllib.request.urlopen(zip_url, timeout=30) as response:
                            if response.status == 200:
                                zip_content = response.read()
                                with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_ref:
                                    zip_ref.extractall(temp_path)

                                # Move content up if nested (GitHub zips usually put content in repo-branch/ folder)
                                items = list(temp_path.glob("*"))
                                if len(items) == 1 and items[0].is_dir():
                                    # Nested dir found, move contents up
                                    nested_dir = items[0]
                                    for item in nested_dir.iterdir():
                                        shutil.move(str(item), str(temp_path))
                                    nested_dir.rmdir()

                                downloaded = True
                                if verbose:
                                    click.echo(f"  Successfully downloaded {branch} branch.")
                                break
                    except Exception as e:
                        if verbose:
                            click.echo(f"  Failed to download {branch}: {e}")
                        continue

                if not downloaded:
                    raise RuntimeError(
                        "Failed to download repository ZIP. Please install Git or check URL."
                    )

            # Set base path for relative path calculation
            base_path = temp_path

            # Find all code files in the cloned/downloaded repo
            # ... (Existing logic continues)

            # Update input_path to point to the cloned repo
            input_path_obj = temp_path
            # FORCE source_type to directory so it falls into the else block below
            source_type = "directory"

            # Find all code files
            files_to_process = []

            for pattern in CODE_PATTERNS:
                for match in glob.glob(str(temp_path / pattern), recursive=True):
                    path_obj = Path(match)
                    if not path_obj.is_file():
                        continue

                    # Skip if matches exclusion patterns
                    if exclude_patterns:
                        should_exclude = False
                        for exclude in exclude_patterns:
                            if Path(exclude).name in str(path_obj):
                                should_exclude = True
                                break
                        if should_exclude:
                            continue

                    files_to_process.append(path_obj)

            files_to_process = sorted(list(set(files_to_process)))

            if verbose:
                click.echo(f"  Found {len(files_to_process)} files in cloned repo.")

        elif source_type == "conversation":
            # It's a conversation file - convert to markdown
            if verbose:
                click.echo("Processing conversation file...")

            from knowgraph.infrastructure.parsing.conversation_ingestor import ingest_conversation

            markdown_content, temp_path = await ingest_conversation(Path(input_path))
            temp_files_to_cleanup.append(temp_path)

            # Treat the generated markdown as a single file
            files_to_process = [temp_path]

        else:
            # Local path - validate and collect files
            input_path_obj = validate_path(input_path, must_exist=True, must_be_file=False)
            base_path = input_path_obj if input_path_obj.is_dir() else input_path_obj.parent

            # Check if directory contains code files (not just markdown)
            if input_path_obj.is_dir():
                # Check for code files
                code_patterns = ["**/*.py", "**/*.js", "**/*.ts", "**/*.java", "**/*.go", "**/*.rs"]
                has_code_files = any(
                    glob.glob(str(input_path_obj / pattern), recursive=True)
                    for pattern in code_patterns
                )

                if has_code_files:
                    # Directory contains code - process files individually
                    if verbose:
                        click.echo("Detected code directory, indexing files individually...")

                    files_to_process = []

                    # Find all code files
                    for pattern in CODE_PATTERNS:
                        for match in glob.glob(str(input_path_obj / pattern), recursive=True):
                            path_obj = Path(match)
                            if not path_obj.is_file():
                                continue

                            # Skip if matches exclusion patterns
                            if exclude_patterns:
                                should_exclude = False
                                for exclude in exclude_patterns:
                                    if Path(exclude).name in str(
                                        path_obj
                                    ):  # Simple check, ideally use pathspec
                                        should_exclude = True
                                        break
                                if should_exclude:
                                    continue

                            files_to_process.append(path_obj)

                    # Remove duplicates while preserving order
                    files_to_process = sorted(list(set(files_to_process)))

                    if verbose:
                        click.echo(f"Found {len(files_to_process)} code files to index.")

                else:
                    # Pure markdown directory - use original logic
                    files_to_process = sorted(
                        [
                            Path(p)
                            for p in glob.glob(str(input_path_obj / "**/*.md"), recursive=True)
                        ]
                    )
            else:
                # Single file
                files_to_process = [input_path_obj]

            if not files_to_process:
                if verbose:
                    click.echo("No files found to index.")
                return

        graph_store_path = validate_path(output_path, must_exist=False, must_be_file=False)

        all_chunks = []
        # file_hashes = {} # This will be replaced by current_hashes

        # Step 3: Check for modifications (Incremental Optimization)
        # Load existing manifest if present
        manifest_path = Path(output_path) / "metadata" / "manifest.json"
        existing_manifest = None
        if manifest_path.exists():
            try:
                existing_manifest = read_manifest(manifest_path)
                if verbose:
                    click.echo(f"Loaded existing manifest (v{existing_manifest.version})")
            except Exception:
                pass

        # Pre-calculate hashes and prepare files
        current_hashes = {}
        files_ready_to_chunk = []

        # We must iterate all found files to check state
        if verbose:
            click.echo("Analysing file states...")

        for file_path in files_to_process:
            try:
                # Read content
                try:
                    content = file_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    # Basic binary check or fallback
                    try:
                        content = file_path.read_text(encoding="latin-1")
                    except Exception:
                        continue  # Skip binary

                # Calculate relative path
                try:
                    relative_path = file_path.relative_to(base_path)
                except ValueError:
                    relative_path = Path(file_path.name)

                # Normalize and Hash
                # Note: We duplicate normalize/hash call here, but it's cheap compared to API
                # Ideally we reuse this result.

                # Simple header logic for normalization context (must match chunk logic for consistency)
                # Determine simple lang for hashing context (optional, but normalization needs content)
                # Actually `normalize_markdown_content` takes raw text.
                # But wait, in the main loop we create `markdown_content` first!
                # So we must replicate that logic to get persistent hash.

                # Moving the markdown wrapping logic HERE to be efficient and consistent.
                lang = EXT_MAP.get(file_path.suffix, "text")
                markdown_wrapper = f"# {relative_path.as_posix()}\n\n```{lang}\n{content}\n```"

                normalized = normalize_markdown_content(markdown_wrapper)
                f_hash = hash_content(normalized)

                current_hashes[str(relative_path.as_posix())] = f_hash
                files_ready_to_chunk.append((file_path, normalized, relative_path))

            except Exception as e:
                if verbose:
                    click.echo(f"Warning during file check {file_path}: {e}")
                continue

        # COMPARE HASHES
        if existing_manifest:
            # Check if identical
            if existing_manifest.file_hashes == current_hashes and existing_manifest.finalized:
                click.echo(
                    f"✓ No changes detected. Graph is up to date ({len(current_hashes)} files)."
                )
                if verbose:
                    click.echo(f"Manifest at {manifest_path} matches current state.")
                return

            elif verbose:
                click.echo("Changes detected. Re-indexing...")

        # Step 4: Iterate PREPARED files
        file_hashes = current_hashes

        for file_path, normalized_content, relative_path in files_ready_to_chunk:
            try:
                if verbose:
                    click.echo(f"✓ Processing {relative_path} ({len(normalized_content)} chars)")

                # We already normalized it above to get the hash
                chunks = chunk_markdown(normalized_content, str(relative_path.as_posix()))
                all_chunks.extend(chunks)

            except Exception as e:
                path_str = str(file_path)
                if verbose:
                    click.echo(f"Error processing {path_str}: {e}")
                continue

        if verbose:
            click.echo(f"✓ Created {len(all_chunks)} chunks from {len(files_ready_to_chunk)} files")

        # Step 3: Build Nodes and Edges
        if not provider:
            try:
                # Default to OpenAI if not provided (e.g. CLI usage)
                from knowgraph.infrastructure.intelligence.openai_provider import OpenAIProvider

                provider = OpenAIProvider()

                builder = SmartGraphBuilder(provider)
            except Exception as e:
                if verbose:
                    click.echo(f"  AI features disabled (Provider init failed): {e}")

                # Fallback to smart builder without provider (uses AST only)
                builder = SmartGraphBuilder(provider=None)
        else:
            builder = SmartGraphBuilder(provider)

        nodes, all_edges = await builder.build(
            all_chunks, str(input_path), "", str(graph_store_path)
        )

        # We still need sparse embeddings for retrieval index
        sparse_embedder = SparseEmbedder()
        sparse_embeddings = {node.id: sparse_embedder.embed_text(node.content) for node in nodes}

        if verbose:
            click.echo(f"✓ Created {len(nodes)} nodes")
            click.echo(f"✓ Created {len(all_edges)} edges")

        # Step 4: Build Sparse Index
        if verbose:
            click.echo("Building Sparse Index...")

        index = SparseIndex()
        for node in nodes:
            if node.id in sparse_embeddings:
                index.add(node.id, sparse_embeddings[node.id])
        index.build()
        index.save(graph_store_path / "index")

        # Step 5: Write to storage
        for node in nodes:
            write_node_json(node, graph_store_path)

        merged_edges = all_edges
        if existing_manifest:
            try:
                from knowgraph.infrastructure.storage.filesystem import read_all_edges

                old_edges = read_all_edges(graph_store_path)

                # Identify nodes that were just re-indexed
                new_node_ids = {n.id for n in nodes}

                # Keep old edges ONLY if they DON'T involve any of the newly re-indexed nodes
                # (because builder already recalculated edges for new nodes including cross-references)
                filtered_old_edges = [
                    e
                    for e in old_edges
                    if e.source not in new_node_ids and e.target not in new_node_ids
                ]

                merged_edges = filtered_old_edges + all_edges
                if verbose:
                    click.echo(
                        f"✓ Merged {len(all_edges)} new edges with {len(filtered_old_edges)} existing edges"
                    )
            except Exception as e:
                if verbose:
                    click.echo(f"  Warning: Could not merge existing edges: {e}")

        write_all_edges(merged_edges, graph_store_path)

        # Step 6: Create Manifest
        semantic_count = len(all_edges)

        manifest = Manifest.create_new(
            edges_filename=EDGES_FILENAME,
            sparse_index_filename="index",
        )
        manifest.node_count = len(nodes)
        manifest.edge_count = len(all_edges)
        manifest.file_hashes = file_hashes
        manifest.semantic_edge_count = semantic_count
        manifest.finalized = True

        # Create backup of existing manifest before overwriting
        try:
            from knowgraph.infrastructure.storage.manifest_backup import ManifestBackupManager

            # Manager expects the directory containing manifest.json (metadata dir)
            metadata_dir = Path(graph_store_path) / "metadata"
            if metadata_dir.exists():
                backup_manager = ManifestBackupManager(metadata_dir)
                backup_path = backup_manager.backup_manifest()
                if verbose and backup_path:
                    click.echo(f"  Manifest backed up to {backup_path}")
        except Exception as e:
            if verbose:
                click.echo(f"  Warning: Could not create manifest backup: {e}")

        write_manifest(manifest, graph_store_path)

        if verbose:
            click.echo(f"✓ Saved manifest (v{manifest.version})")

        # POST-INDEX HOOKS
        if link_conversations or incremental:
            if verbose:
                click.echo("\n" + "=" * 60)
                click.echo("POST-INDEX PROCESSING")
                click.echo("=" * 60)

        # Auto-link conversations
        if link_conversations:
            if verbose:
                click.echo("\n🔗 Auto-linking conversations...")
            try:
                from knowgraph.application.indexing.post_index_hooks import auto_link_conversations

                conv_stats = await auto_link_conversations(
                    Path(graph_store_path),
                    workspace_path=Path(input_path) if not source_type == "repository" else None,
                )

                if verbose:
                    click.echo(f"  Conversations found: {conv_stats['conversations_found']}")
                    click.echo(f"  Conversations linked: {conv_stats['conversations_linked']}")
                    click.echo(f"  Edges created: {conv_stats['edges_created']}")
                    if conv_stats["errors"] > 0:
                        click.echo(f"  Errors: {conv_stats['errors']}")
            except Exception as e:
                if verbose:
                    click.echo(f"  ⚠️  Conversation linking failed: {e}")

        # Collect enhanced statistics
        if verbose:
            click.echo("\n" + "=" * 60)
            click.echo("INDEXING STATISTICS")
            click.echo("=" * 60)

            try:
                from knowgraph.application.indexing.post_index_hooks import collect_index_stats

                stats = collect_index_stats(Path(graph_store_path))

                click.echo(f"\n📊 Nodes by Type:")
                click.echo(f"  Code nodes: {stats['code_nodes']}")
                click.echo(f"  Markdown nodes: {stats['markdown_nodes']}")
                if stats["conversation_nodes"] > 0:
                    click.echo(f"  Conversation nodes: {stats['conversation_nodes']}")
                if stats["bookmark_nodes"] > 0:
                    click.echo(f"  Bookmarks: {stats['bookmark_nodes']}")
                click.echo(f"  Total nodes: {stats['total_nodes']}")
                click.echo(f"\n📈 Edges: {stats['total_edges']}")
            except Exception:
                pass

        elapsed = time.time() - start_time
        if verbose:
            click.echo(f"\n✅ Indexing completed in {elapsed:.1f}s")
            click.echo(f"Graph stored in: {graph_store_path}")

    except RepositoryIngestorError as e:
        click.echo(f"Repository ingestion error: {e}", err=True)
        raise

    finally:
        # Cleanup temporary files and directories
        for temp_item in temp_files_to_cleanup:
            try:
                if temp_item.exists():
                    if temp_item.is_dir():
                        shutil.rmtree(temp_item)
                    else:
                        temp_item.unlink()
            except Exception:
                pass  # Ignore cleanup errors


@click.command()
@click.argument("input_path", type=str)
@click.option(
    "--output",
    "-o",
    default=str(DEFAULT_GRAPH_STORE_PATH),
    help="Output path for the graph store",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option(
    "--link-conversations",
    is_flag=True,
    help="Auto-discover and link conversations to code after indexing",
)
@click.option(
    "--incremental",
    is_flag=True,
    help="Only index new/modified files (uses checkpoint for faster re-indexing)",
)
def index_command(
    input_path: str,
    output: str,
    verbose: bool,
    link_conversations: bool,
    incremental: bool,
) -> None:
    """Index markdown files, code, or repositories into a knowledge graph.

    Enhanced with:
    - Auto conversation discovery and linking (--link-conversations)
    - Incremental indexing for faster updates (--incremental)
    """
    import asyncio

    try:
        asyncio.run(
            run_index(
                input_path,
                output,
                verbose,
                link_conversations=link_conversations,
                incremental=incremental,
            )
        )
    except Exception as error:
        click.echo(f"Error: {error}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    index_command()
