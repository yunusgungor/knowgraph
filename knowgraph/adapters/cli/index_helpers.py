"""Helper functions for source detection and preparation in indexing.

Extracted from run_index to reduce complexity and improve maintainability.
"""

import asyncio
import glob
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import click

from knowgraph.infrastructure.parsing.repo_ingestor import detect_source_type

# Global list to track temporary files for cleanup
_temp_cleanup_registry: list[Path] = []


def _log_verbose(verbose: bool, message: str) -> None:
    """Log message if verbose mode enabled."""
    if verbose:
        click.echo(message)


async def _handle_repository_source(
    input_path: str,
    verbose: bool,
) -> tuple[str, Path, list[Path]]:
    """Handle repository URL input - clone and prepare files.

    Args:
        input_path: Repository URL
        verbose: Enable verbose logging

    Returns:
        (source_type, base_path, files_to_process)
    """
    _log_verbose(verbose, "Remote repository detected...")

    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix="knowgraph_repo_")
    temp_path = Path(temp_dir)
    _temp_cleanup_registry.append(temp_path)

    # Try git clone first
    if shutil.which("git") is not None:
        _log_verbose(verbose, "Cloning repository (git)...")
        subprocess.run(  # noqa: S603
            ["git", "clone", "--depth", "1", input_path, str(temp_path)],
            check=True,
            capture_output=True,
        )
    else:
        # Fallback to ZIP download
        _log_verbose(verbose, "Git not found. Attempting ZIP download...")
        await _download_repository_zip(input_path, temp_path, verbose)

    # Collect files from cloned repo
    files = _collect_code_files_from_directory(temp_path, None, verbose)

    return "directory", temp_path, files


async def _download_repository_zip(
    repo_url: str,
    target_path: Path,
    verbose: bool,
) -> None:
    """Download repository as ZIP (fallback when git unavailable)."""
    import io
    import urllib.request
    import zipfile

    # Normalize URL
    normalized_url = repo_url.rstrip("/")
    if normalized_url.endswith(".git"):
        normalized_url = normalized_url[:-4]

    # Try main and master branches
    branches = ["main", "master"]
    downloaded = False

    for branch in branches:
        zip_url = f"{normalized_url}/archive/refs/heads/{branch}.zip"
        try:
            _log_verbose(verbose, f"  Trying {branch} branch...")

            with urllib.request.urlopen(zip_url, timeout=30) as response:  # noqa: S310
                if response.status == 200:
                    zip_content = response.read()
                    with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_ref:
                        zip_ref.extractall(target_path)

                    # Move content up if nested
                    items = list(target_path.glob("*"))
                    if len(items) == 1 and items[0].is_dir():
                        nested_dir = items[0]
                        for item in nested_dir.iterdir():
                            shutil.move(str(item), str(target_path))
                        nested_dir.rmdir()

                    downloaded = True
                    _log_verbose(verbose, f"  Successfully downloaded {branch} branch.")
                    break
        except Exception as e:
            _log_verbose(verbose, f"  Failed to download {branch}: {e}")
            continue

    if not downloaded:
        raise RuntimeError("Failed to download repository ZIP. Please install Git or check URL.")


async def _handle_conversation_source(
    input_path: str,
    verbose: bool,
) -> tuple[str, Path, list[Path]]:
    """Handle conversation file input - convert to markdown.

    Args:
        input_path: Path to conversation file
        verbose: Enable verbose logging

    Returns:
        (source_type, base_path, files_to_process)
    """
    _log_verbose(verbose, "Processing conversation file...")

    from knowgraph.infrastructure.parsing.conversation_ingestor import ingest_conversation

    _, temp_path = await ingest_conversation(Path(input_path))
    _temp_cleanup_registry.append(temp_path)

    return "conversation", temp_path.parent, [temp_path]


def _handle_local_source(
    input_path: str,
    exclude_patterns: list[str] | None,
    verbose: bool,
) -> tuple[str, Path, list[Path]]:
    """Handle local file/directory input.

    Args:
        input_path: Local file or directory path
        exclude_patterns: Patterns to exclude
        verbose: Enable verbose logging

    Returns:
        (source_type, base_path, files_to_process)
    """
    from knowgraph.shared.security import validate_path

    input_path_obj = validate_path(input_path, must_exist=True, must_be_file=False)
    base_path = input_path_obj if input_path_obj.is_dir() else input_path_obj.parent

    if input_path_obj.is_dir():
        # Check if directory contains code files
        code_patterns = ["**/*.py", "**/*.js", "**/*.ts", "**/*.java", "**/*.go", "**/*.rs"]
        has_code_files = any(
            glob.glob(str(input_path_obj / pattern), recursive=True) for pattern in code_patterns
        )

        if has_code_files:
            _log_verbose(verbose, "Detected code directory, indexing files individually...")
            files = _collect_code_files_from_directory(input_path_obj, exclude_patterns, verbose)
        else:
            # Pure markdown directory
            files = sorted(
                [Path(p) for p in glob.glob(str(input_path_obj / "**/*.md"), recursive=True)]
            )
    else:
        # Single file
        files = [input_path_obj]

    if not files:
        _log_verbose(verbose, "No files found to index.")

    return "directory", base_path, files


def _collect_code_files_from_directory(
    directory: Path,
    exclude_patterns: list[str] | None,
    verbose: bool,
) -> list[Path]:
    """Collect all code files from directory with smart filtering.

    Args:
        directory: Directory to search
        exclude_patterns: Patterns to exclude
        verbose: Enable verbose logging

    Returns:
        List of file paths to process
    """
    # Import LANGUAGE_MAP to derive CODE_PATTERNS
    from knowgraph.adapters.cli.index_command import LANGUAGE_MAP
    from knowgraph.infrastructure.filtering.file_filter import should_skip_file

    # Generate CODE_PATTERNS from LANGUAGE_MAP
    CODE_PATTERNS = [f"**/*.{ext}" for ext in LANGUAGE_MAP]

    files_to_process = []

    for pattern in CODE_PATTERNS:
        for match in glob.glob(str(directory / pattern), recursive=True):
            path_obj = Path(match)

            # Use smart filtering
            if should_skip_file(path_obj):
                continue

            # Skip if matches exclusion patterns
            if exclude_patterns:
                should_exclude = False
                for exclude in exclude_patterns:
                    if exclude in str(path_obj):
                        should_exclude = True
                        break
                if should_exclude:
                    continue

            files_to_process.append(path_obj)

    files_to_process = sorted(set(files_to_process))

    _log_verbose(verbose, f"Found {len(files_to_process)} files to index.")

    return files_to_process


async def detect_and_prepare_source(
    input_path: str,
    verbose: bool,
    exclude_patterns: list[str] | None = None,
    access_token: str | None = None,
) -> tuple[str, Path, list[Path]]:
    """Detect source type and prepare for indexing.

    Main orchestrator for source preparation that delegates to
    specific handlers based on source type.

    Args:
        input_path: Input path or URL
        verbose: Enable verbose logging
        exclude_patterns: File patterns to exclude
        access_token: GitHub access token (unused currently)

    Returns:
        (source_type, base_path, files_to_process)
    """
    source_type = detect_source_type(input_path)

    _log_verbose(verbose, f"Detected source type: {source_type}")
    _log_verbose(verbose, f"Indexing {input_path} (AI Mode)...")

    if source_type == "repository" or (
        source_type == "directory" and not Path(input_path).exists()
    ):
        return await _handle_repository_source(input_path, verbose)
    elif source_type == "conversation":
        return await _handle_conversation_source(input_path, verbose)
    else:
        return _handle_local_source(input_path, exclude_patterns, verbose)


def cleanup_temp_files() -> None:
    """Clean up all registered temporary files and directories."""
    for temp_item in _temp_cleanup_registry:
        try:
            if temp_item.exists():
                if temp_item.is_dir():
                    shutil.rmtree(temp_item)
                else:
                    temp_item.unlink()
        except Exception:
            pass  # Ignore cleanup errors

    _temp_cleanup_registry.clear()


# Hash Preparation & File Processing


async def prepare_files_and_hashes(files, base_path, verbose):
    from knowgraph.adapters.cli.index_command import EXT_MAP
    from knowgraph.application.indexing.graph_builder import normalize_markdown_content
    from knowgraph.infrastructure.cache.indexing_cache import IndexingCache
    from knowgraph.infrastructure.filtering.file_filter import filter_files
    from knowgraph.infrastructure.parsing.hasher import hash_content

    # Filter out unnecessary files first
    files = filter_files(files)

    current_hashes, files_ready = {}, []
    _log_verbose(verbose, "Analysing file states...")

    # Initialize cache
    cache_dir = base_path if isinstance(base_path, Path) else Path(base_path)
    cache = IndexingCache(cache_dir)

    total_files = len(files)
    cached_count = 0

    click.echo(f"Processing {total_files} files (with smart caching)...")

    async def process_single_file(file_path, index):
        """Process a single file asynchronously with caching."""
        nonlocal cached_count
        try:
            # Show progress every 10 files
            if (index + 1) % 10 == 0 or index == total_files - 1:
                click.echo(f"  [{index + 1}/{total_files}] Reading (cached: {cached_count})...", nl=False)
                click.echo("\r", nl=False)

            # Read file asynchronously
            try:
                loop = asyncio.get_event_loop()
                content = await loop.run_in_executor(None, file_path.read_text, "utf-8")
            except UnicodeDecodeError:
                try:
                    content = await loop.run_in_executor(None, file_path.read_text, "latin-1")
                except Exception:  # noqa: S110
                    return None

            try:
                relative_path = file_path.relative_to(base_path)
            except ValueError:
                relative_path = Path(file_path.name)

            lang = EXT_MAP.get(file_path.suffix, "text")
            markdown_wrapper = f"# {relative_path.as_posix()}\n\n```{lang}\n{content}\n```"
            normalized = normalize_markdown_content(markdown_wrapper)
            file_hash = hash_content(normalized)

            # Check cache
            if cache.is_cached(file_path, file_hash):
                cached_count += 1
                _log_verbose(verbose, f"  ✓ Using cache for {relative_path}")
                # Still return the data for manifest tracking
                return (file_path, normalized, relative_path, file_hash, True)  # True = from cache

            return (file_path, normalized, relative_path, file_hash, False)  # False = needs processing
        except Exception as e:
            _log_verbose(verbose, f"Warning: {file_path}: {e}")
            return None

    # Process all files in parallel
    results = await asyncio.gather(*[process_single_file(f, i) for i, f in enumerate(files)])

    click.echo(f"\n✓ Processed {total_files} files ({cached_count} from cache)")

    cached_files = []  # Track cached files
    file_hash_map = {}  # Map file_path to hash
    for result in results:
        if result is not None:
            file_path, normalized, relative_path, file_hash, from_cache = result
            current_hashes[str(relative_path.as_posix())] = file_hash
            file_hash_map[str(file_path)] = file_hash  # Store hash mapping
            if from_cache:
                cached_files.append(file_path)
            else:
                files_ready.append((file_path, normalized, relative_path))

    return current_hashes, files_ready, cached_files, cache, file_hash_map


def load_existing_manifest(output_path, verbose):
    from knowgraph.infrastructure.storage.manifest import read_manifest

    manifest_path = Path(output_path) / "metadata" / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = read_manifest(manifest_path)
        _log_verbose(verbose, f"Loaded manifest (v{manifest.version})")  # type: ignore[union-attr]
        return manifest
    except Exception:  # noqa: S110
        return None


def should_skip_indexing(existing_manifest, current_hashes, verbose):
    if not existing_manifest:
        return False
    if existing_manifest.file_hashes == current_hashes and existing_manifest.finalized:
        version_str = getattr(existing_manifest, "version", "unknown")  # type: ignore[union-attr]
        click.echo(f"✓ No changes detected ({len(current_hashes)} files, v{version_str}).")
        return True
    _log_verbose(verbose, "Changes detected. Re-indexing...")
    return False


# ============================================================================
# File Chunking
# ============================================================================


async def chunk_files(files_ready, verbose):
    """Chunk all prepared files in parallel."""
    from knowgraph.infrastructure.parsing.chunker import chunk_markdown

    total_files = len(files_ready)
    click.echo(f"Chunking {total_files} files...")

    async def chunk_single_file(file_path, normalized_content, relative_path, index):
        """Chunk a single file asynchronously."""
        try:
            # Show progress
            if (index + 1) % 10 == 0 or index == total_files - 1:
                click.echo(f"  [{index + 1}/{total_files}] Chunking...", nl=False)
                click.echo("\r", nl=False)

            _log_verbose(verbose, f"✓ Processing {relative_path} ({len(normalized_content)} chars)")
            # Run chunking in executor to avoid blocking
            loop = asyncio.get_event_loop()
            chunks = await loop.run_in_executor(
                None, chunk_markdown, normalized_content, str(relative_path.as_posix())
            )
            return chunks
        except Exception as e:
            _log_verbose(verbose, f"Error processing {file_path}: {e}")
            return []

    # Process all files in parallel
    chunk_results = await asyncio.gather(
        *[chunk_single_file(fp, nc, rp, i) for i, (fp, nc, rp) in enumerate(files_ready)]
    )

    all_chunks = []
    for chunks in chunk_results:
        all_chunks.extend(chunks)

    click.echo(f"\n✓ Created {len(all_chunks)} chunks from {len(files_ready)} files")
    _log_verbose(verbose, f"✓ Created {len(all_chunks)} chunks from {len(files_ready)} files")
    return all_chunks


# ============================================================================
# Graph Building
# ============================================================================


async def build_knowledge_graph(chunks, input_path, graph_store_path, provider, verbose, base_path=None, file_hash_map=None):
    """Build knowledge graph from chunks."""
    from knowgraph.application.indexing.graph_builder import SmartGraphBuilder
    from knowgraph.infrastructure.cache.indexing_cache import IndexingCache

    if not provider:
        try:
            from knowgraph.infrastructure.intelligence.openai_provider import OpenAIProvider

            provider = OpenAIProvider()
        except Exception as e:
            _log_verbose(verbose, f"AI features disabled: {e}")
            provider = None

    if not chunks:
        click.echo("✓ No new chunks to process (all files cached)")
        return [], [], None  # Return cache object too

    click.echo(f"Building knowledge graph from {len(chunks)} chunks...")
    builder = SmartGraphBuilder(provider)
    nodes, edges = await builder.build(chunks, str(input_path), "", str(graph_store_path))

    # Initialize cache and save results
    cache = None
    if base_path and file_hash_map:
        cache_dir = base_path if isinstance(base_path, Path) else Path(base_path)
        cache = IndexingCache(cache_dir)

        # Group nodes by file and cache them
        from collections import defaultdict
        nodes_by_file = defaultdict(list)
        for node in nodes:
            if node.path:
                nodes_by_file[node.path].append(node.to_dict())

        # Cache each file's nodes with the correct file hash
        for file_path_str, file_nodes in nodes_by_file.items():
            try:
                file_path = Path(file_path_str)
                # Get the correct file hash from our mapping
                file_hash = file_hash_map.get(str(file_path))
                if file_hash and file_nodes:
                    cache.cache_result(file_path, file_hash, file_nodes)
            except Exception as e:
                _log_verbose(verbose, f"Warning: Could not cache {file_path_str}: {e}")

    click.echo(f"✓ Created {len(nodes)} nodes and {len(edges)} edges")
    _log_verbose(verbose, f"✓ Created {len(nodes)} nodes")
    _log_verbose(verbose, f"✓ Created {len(edges)} edges")

    return nodes, edges, cache


# ============================================================================
# Storage Operations
# ============================================================================


async def write_graph_to_storage(nodes, edges, existing_manifest, graph_store_path, verbose):
    """Write graph to storage and build search index (async optimized)."""
    from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder
    from knowgraph.infrastructure.search.sparse_index import SparseIndex
    from knowgraph.infrastructure.storage.filesystem import (
        read_all_edges_async,
        write_all_edges_async,
        write_node_json_async,
    )

    # Skip if no new nodes to write
    if not nodes:
        click.echo("✓ No new nodes to write (all cached)")
        return {}

    click.echo("Building sparse index...")
    sparse_embedder = SparseEmbedder()
    sparse_embeddings = {node.id: sparse_embedder.embed_text(node.content) for node in nodes}

    _log_verbose(verbose, "Building Sparse Index...")
    index = SparseIndex()
    for node in nodes:
        if node.id in sparse_embeddings:
            index.add(node.id, sparse_embeddings[node.id])
    index.build()
    # Run index save in executor (it's sync I/O)
    await asyncio.get_event_loop().run_in_executor(None, index.save, graph_store_path / "index")

    click.echo(f"Writing {len(nodes)} nodes to storage...")
    # Write all nodes in parallel using async
    await asyncio.gather(*[write_node_json_async(node, graph_store_path) for node in nodes])

    merged_edges = edges
    if existing_manifest:
        try:
            click.echo("Merging with existing edges...")
            old_edges = await read_all_edges_async(graph_store_path)
            new_node_ids = {n.id for n in nodes}
            filtered_old_edges = [
                e
                for e in old_edges
                if e.source not in new_node_ids and e.target not in new_node_ids
            ]
            merged_edges = filtered_old_edges + edges
            _log_verbose(
                verbose,
                f"✓ Merged {len(edges)} new edges with {len(filtered_old_edges)} existing edges",
            )
        except Exception as e:
            _log_verbose(verbose, f"Warning: Could not merge existing edges: {e}")

    click.echo(f"Writing {len(merged_edges)} edges to storage...")
    await write_all_edges_async(merged_edges, graph_store_path)
    return sparse_embeddings


# ============================================================================
# Manifest Creation
# ============================================================================


async def create_and_save_manifest(nodes, edges, file_hashes, graph_store_path, verbose):
    """Create and save manifest with automatic backup."""
    from knowgraph.config import EDGES_FILENAME
    from knowgraph.infrastructure.storage.manifest import Manifest, write_manifest

    try:
        from knowgraph.infrastructure.storage.manifest_backup import ManifestBackupManager

        metadata_dir = Path(graph_store_path) / "metadata"
        if metadata_dir.exists():
            backup_manager = ManifestBackupManager(metadata_dir)
            backup_path = backup_manager.backup_manifest()
            if verbose and backup_path:
                _log_verbose(verbose, f"Manifest backed up to {backup_path}")
    except Exception as e:
        _log_verbose(verbose, f"Warning: Could not create manifest backup: {e}")

    manifest = Manifest.create_new(edges_filename=EDGES_FILENAME, sparse_index_filename="index")
    manifest.node_count = len(nodes)
    manifest.edge_count = len(edges)
    manifest.file_hashes = file_hashes
    manifest.semantic_edge_count = len(edges)
    manifest.finalized = True

    write_manifest(manifest, graph_store_path)
    _log_verbose(verbose, f"✓ Saved manifest (v{manifest.version})")


# ============================================================================
# Post-Index Hooks
# ============================================================================


async def run_post_index_hooks(
    link_conversations, input_path, source_type, graph_store_path, verbose
):
    """Run post-indexing hooks (conversation linking, stats)."""
    if not (link_conversations or verbose):
        return

    _log_verbose(verbose, "\n" + "=" * 60)
    _log_verbose(verbose, "POST-INDEX PROCESSING")
    _log_verbose(verbose, "=" * 60)

    if link_conversations:
        _log_verbose(verbose, "\n🔗 Auto-linking conversations...")
        try:
            from knowgraph.application.indexing.post_index_hooks import auto_link_conversations

            conv_stats = await auto_link_conversations(
                Path(graph_store_path),
                workspace_path=Path(input_path) if source_type != "repository" else None,
            )
            _log_verbose(verbose, f"  Conversations found: {conv_stats['conversations_found']}")
            _log_verbose(verbose, f"  Conversations linked: {conv_stats['conversations_linked']}")
            _log_verbose(verbose, f"  Edges created: {conv_stats['edges_created']}")
            if conv_stats["errors"] > 0:
                _log_verbose(verbose, f"  Errors: {conv_stats['errors']}")
        except Exception as e:
            _log_verbose(verbose, f"  ⚠️  Conversation linking failed: {e}")

    if verbose:
        _log_verbose(verbose, "\n" + "=" * 60)
        _log_verbose(verbose, "INDEXING STATISTICS")
        _log_verbose(verbose, "=" * 60)
        try:
            from knowgraph.application.indexing.post_index_hooks import collect_index_stats

            stats = collect_index_stats(Path(graph_store_path))
            click.echo("\n📊 Nodes by Type:")
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


def log_completion(start_time, graph_store_path, verbose):
    """Log indexing completion statistics."""
    elapsed = time.time() - start_time

    # Show cache statistics
    try:
        from knowgraph.infrastructure.cache.indexing_cache import IndexingCache
        cache = IndexingCache(Path(graph_store_path).parent)
        stats = cache.get_stats()
        click.echo(f"\n📊 Cache: {stats['cached_files']} files ({stats['cache_size_mb']:.1f} MB)")
    except Exception:
        pass

    click.echo(f"\n✅ Indexing completed in {elapsed:.1f}s")
    _log_verbose(verbose, f"\n✅ Indexing completed in {elapsed:.1f}s")
    _log_verbose(verbose, f"Graph stored in: {graph_store_path}")
