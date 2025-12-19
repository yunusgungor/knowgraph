"""Helper functions for source detection and preparation in indexing.

Extracted from run_index to reduce complexity and improve maintainability.
"""

import glob
import shutil
import subprocess
import tempfile
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
        subprocess.run(
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

            with urllib.request.urlopen(zip_url, timeout=30) as response:
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
    """Collect all code files from directory.

    Args:
        directory: Directory to search
        exclude_patterns: Patterns to exclude
        verbose: Enable verbose logging

    Returns:
        List of file paths to process
    """
    # Import LANGUAGE_MAP to derive CODE_PATTERNS
    from knowgraph.adapters.cli.index_command import LANGUAGE_MAP

    # Generate CODE_PATTERNS from LANGUAGE_MAP
    CODE_PATTERNS = [f"**/*.{ext}" for ext in LANGUAGE_MAP.keys()]

    files_to_process = []

    for pattern in CODE_PATTERNS:
        for match in glob.glob(str(directory / pattern), recursive=True):
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

import time


async def prepare_files_and_hashes(files, base_path, verbose):
    from knowgraph.adapters.cli.index_command import EXT_MAP
    from knowgraph.application.indexing.graph_builder import normalize_markdown_content
    from knowgraph.infrastructure.parsing.hasher import hash_content

    current_hashes, files_ready = {}, []
    _log_verbose(verbose, "Analysing file states...")

    for file_path in files:
        try:
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    content = file_path.read_text(encoding="latin-1")
                except:
                    continue

            try:
                relative_path = file_path.relative_to(base_path)
            except ValueError:
                relative_path = Path(file_path.name)

            lang = EXT_MAP.get(file_path.suffix, "text")
            markdown_wrapper = f"# {relative_path.as_posix()}\n\n```{lang}\n{content}\n```"
            normalized = normalize_markdown_content(markdown_wrapper)
            file_hash = hash_content(normalized)

            current_hashes[str(relative_path.as_posix())] = file_hash
            files_ready.append((file_path, normalized, relative_path))
        except Exception as e:
            _log_verbose(verbose, f"Warning: {file_path}: {e}")

    return current_hashes, files_ready


def load_existing_manifest(output_path, verbose):
    from knowgraph.infrastructure.storage.manifest import read_manifest

    manifest_path = Path(output_path) / "metadata" / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = read_manifest(manifest_path)
        _log_verbose(verbose, f"Loaded manifest (v{manifest.version})")
        return manifest
    except:
        return None


def should_skip_indexing(existing_manifest, current_hashes, verbose):
    if not existing_manifest:
        return False
    if existing_manifest.file_hashes == current_hashes and existing_manifest.finalized:
        click.echo(f"✓ No changes detected ({len(current_hashes)} files).")
        return True
    _log_verbose(verbose, "Changes detected. Re-indexing...")
    return False


# ============================================================================
# File Chunking
# ============================================================================


async def chunk_files(files_ready, verbose):
    """Chunk all prepared files."""
    from knowgraph.infrastructure.parsing.chunker import chunk_markdown

    all_chunks = []

    for file_path, normalized_content, relative_path in files_ready:
        try:
            _log_verbose(verbose, f"✓ Processing {relative_path} ({len(normalized_content)} chars)")
            chunks = chunk_markdown(normalized_content, str(relative_path.as_posix()))
            all_chunks.extend(chunks)
        except Exception as e:
            _log_verbose(verbose, f"Error processing {file_path}: {e}")
            continue

    _log_verbose(verbose, f"✓ Created {len(all_chunks)} chunks from {len(files_ready)} files")
    return all_chunks


# ============================================================================
# Graph Building
# ============================================================================


async def build_knowledge_graph(chunks, input_path, graph_store_path, provider, verbose):
    """Build knowledge graph from chunks."""
    from knowgraph.application.indexing.graph_builder import SmartGraphBuilder

    if not provider:
        try:
            from knowgraph.infrastructure.intelligence.openai_provider import OpenAIProvider

            provider = OpenAIProvider()
        except Exception as e:
            _log_verbose(verbose, f"AI features disabled: {e}")
            provider = None

    builder = SmartGraphBuilder(provider)
    nodes, edges = await builder.build(chunks, str(input_path), "", str(graph_store_path))

    _log_verbose(verbose, f"✓ Created {len(nodes)} nodes")
    _log_verbose(verbose, f"✓ Created {len(edges)} edges")

    return nodes, edges


# ============================================================================
# Storage Operations
# ============================================================================


async def write_graph_to_storage(nodes, edges, existing_manifest, graph_store_path, verbose):
    """Write graph to storage and build search index."""
    from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder
    from knowgraph.infrastructure.search.sparse_index import SparseIndex
    from knowgraph.infrastructure.storage.filesystem import (
        write_node_json,
        write_all_edges,
        read_all_edges,
    )

    sparse_embedder = SparseEmbedder()
    sparse_embeddings = {node.id: sparse_embedder.embed_text(node.content) for node in nodes}

    _log_verbose(verbose, "Building Sparse Index...")
    index = SparseIndex()
    for node in nodes:
        if node.id in sparse_embeddings:
            index.add(node.id, sparse_embeddings[node.id])
    index.build()
    index.save(graph_store_path / "index")

    for node in nodes:
        write_node_json(node, graph_store_path)

    merged_edges = edges
    if existing_manifest:
        try:
            old_edges = read_all_edges(graph_store_path)
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

    write_all_edges(merged_edges, graph_store_path)
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


def log_completion(start_time, graph_store_path, verbose):
    """Log indexing completion statistics."""
    elapsed = time.time() - start_time
    _log_verbose(verbose, f"\n✅ Indexing completed in {elapsed:.1f}s")
    _log_verbose(verbose, f"Graph stored in: {graph_store_path}")
