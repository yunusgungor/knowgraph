"""MCP methods for version management."""

import mcp.types as types

from knowgraph.infrastructure.storage.version_diff import VersionDiffEngine
from knowgraph.infrastructure.storage.version_history import VersionHistoryManager


async def list_graph_versions(
    graph_path: str,
    limit: int = 50,
) -> list[types.TextContent]:
    """List all versions in the knowledge graph.

    Args:
        graph_path: Path to graph store directory
        limit: Maximum number of versions to return

    Returns:
        List of text content with version information
    """
    from pathlib import Path

    try:
        version_mgr = VersionHistoryManager(Path(graph_path))
        versions = version_mgr.list_versions(limit=limit)

        if not versions:
            return [
                types.TextContent(
                    type="text",
                    text="No versions found in graph history.",
                )
            ]

        # Build response
        lines = [f"Found {len(versions)} versions:\n"]

        for v in versions:
            lines.append(f"  {v.version_id}:")
            lines.append(f"    Created: {v.created_at_iso}")
            lines.append(
                f"    Nodes: {v.node_count:,}  Edges: {v.edge_count:,}  Files: {v.file_count}"
            )

            if v.file_changes.total_changes > 0:
                fc = v.file_changes
                lines.append(
                    f"    Changes: +{len(fc.added)} ~{len(fc.modified)} -{len(fc.deleted)}"
                )

            lines.append("")

        return [types.TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        return [
            types.TextContent(
                type="text",
                text=f"Error listing versions: {e!s}",
            )
        ]


async def get_version_info(
    graph_path: str,
    version_id: str,
) -> list[types.TextContent]:
    """Get detailed information abouta specific version.

    Args:
        graph_path: Path to graph store directory
        version_id: Version identifier (e.g., "v1", "v2")

    Returns:
        List of text content with version details
    """
    from pathlib import Path

    try:
        version_mgr = VersionHistoryManager(Path(graph_path))
        version = version_mgr.get_version(version_id)

        if not version:
            return [
                types.TextContent(
                    type="text",
                    text=f"Version '{version_id}' not found.",
                )
            ]

        # Build detailed response
        lines = []
        lines.append(f"Version {version.version_id}:")
        lines.append(f"  Created: {version.created_at_iso}")
        lines.append(f"  Hash: {version.manifest_hash}")
        lines.append("")
        lines.append("Graph Statistics:")
        lines.append(f"  Nodes: {version.node_count:,}")
        lines.append(f"  Edges: {version.edge_count:,}")
        lines.append(f"  Files: {version.file_count:,}")

        fc = version.file_changes
        if fc.total_changes > 0:
            lines.append("")
            lines.append("File Changes:")
            if fc.added:
                lines.append(f"  Added: {len(fc.added)} files")
                for f in sorted(fc.added)[:5]:
                    lines.append(f"    + {f}")
                if len(fc.added) > 5:
                    lines.append(f"    ... and {len(fc.added) - 5} more")

            if fc.modified:
                lines.append(f"  Modified: {len(fc.modified)} files")
                for f in sorted(fc.modified)[:5]:
                    lines.append(f"    M {f}")
                if len(fc.modified) > 5:
                    lines.append(f"    ... and {len(fc.modified) - 5} more")

            if fc.deleted:
                lines.append(f"  Deleted: {len(fc.deleted)} files")
                for f in sorted(fc.deleted)[:5]:
                    lines.append(f"    - {f}")
                if len(fc.deleted) > 5:
                    lines.append(f"    ... and {len(fc.deleted) - 5} more")

        return [types.TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        return [
            types.TextContent(
                type="text",
                text=f"Error getting version info: {e!s}",
            )
        ]


async def diff_graph_versions(
    graph_path: str,
    version1: str,
    version2: str,
) -> list[types.TextContent]:
    """Compare two versions and show differences.

    Args:
        graph_path: Path to graph store directory
        version1: First version ID
        version2: Second version ID

    Returns:
        List of text content with diff report
    """
    from pathlib import Path

    try:
        version_mgr = VersionHistoryManager(Path(graph_path))

        v1 = version_mgr.get_version(version1)
        if not v1:
            return [
                types.TextContent(
                    type="text",
                    text=f"Version '{version1}' not found.",
                )
            ]

        v2 = version_mgr.get_version(version2)
        if not v2:
            return [
                types.TextContent(
                    type="text",
                    text=f"Version '{version2}' not found.",
                )
            ]

        # Generate diff
        diff_engine = VersionDiffEngine()
        diff = diff_engine.diff_versions(v1, v2)
        report = diff_engine.format_diff_report(diff)

        return [types.TextContent(type="text", text=report)]

    except Exception as e:
        return [
            types.TextContent(
                type="text",
                text=f"Error diffing versions: {e!s}",
            )
        ]
