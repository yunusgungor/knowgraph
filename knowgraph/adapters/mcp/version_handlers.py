from pathlib import Path
from typing import Any

import mcp.types as types

from knowgraph.adapters.mcp.utils import resolve_graph_path
from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
from knowgraph.shared.refactoring import validate_required_argument


# Version management handlers
async def handle_list_versions(
    arguments: dict[str, Any],
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_list_versions tool."""
    from knowgraph.adapters.mcp.version_methods import list_graph_versions

    graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
    graph_path = resolve_graph_path(graph_path_arg, project_root)
    limit = arguments.get("limit", 50)

    return await list_graph_versions(str(graph_path), limit)


async def handle_version_info(
    arguments: dict[str, Any],
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_version_info tool."""
    from knowgraph.adapters.mcp.version_methods import get_version_info

    if error := validate_required_argument(arguments, "version_id"):
        return [types.TextContent(type="text", text=error)]

    graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
    graph_path = resolve_graph_path(graph_path_arg, project_root)
    version_id = arguments["version_id"]

    return await get_version_info(str(graph_path), version_id)


async def handle_diff_versions(
    arguments: dict[str, Any],
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_diff_versions tool."""
    from knowgraph.adapters.mcp.version_methods import diff_graph_versions

    if error := validate_required_argument(arguments, "version1"):
        return [types.TextContent(type="text", text=error)]
    if error := validate_required_argument(arguments, "version2"):
        return [types.TextContent(type="text", text=error)]

    graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
    graph_path = resolve_graph_path(graph_path_arg, project_root)
    version1 = arguments["version1"]
    version2 = arguments["version2"]

    return await diff_graph_versions(str(graph_path), version1, version2)


# Add rollback handler to version_handlers.py
async def handle_rollback(
    arguments: dict[str, Any],
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_rollback tool."""
    from knowgraph.infrastructure.storage.version_rollback import RollbackManager

    if error := validate_required_argument(arguments, "version_id"):
        return [types.TextContent(type="text", text=error)]

    graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
    graph_path = resolve_graph_path(graph_path_arg, project_root)
    version_id = arguments["version_id"]
    create_backup = arguments.get("create_backup", True)
    force = arguments.get("force", False)

    try:
        rollback_mgr = RollbackManager(graph_path)
        result = rollback_mgr.rollback_to_version(
            target_version_id=version_id,
            create_backup=create_backup,
            force=force,
        )

        if result.success:
            response_lines = [
                "✅ Rollback Successful!",
                "",
                f"From: {result.from_version}",
                f"To: {result.to_version}",
            ]

            if result.backup_path:
                response_lines.append(f"Backup: {result.backup_path}")

            response_lines.append("")
            response_lines.append(result.message)

            if result.errors:
                response_lines.append("")
                response_lines.append("⚠️ Warnings:")
                for error in result.errors:
                    response_lines.append(f"  • {error}")

            return [types.TextContent(type="text", text="\n".join(response_lines))]
        else:
            error_lines = [
                "❌ Rollback Failed",
                "",
                result.message,
            ]
            if result.errors:
                error_lines.append("")
                error_lines.append("Errors:")
                for error in result.errors:
                    error_lines.append(f"  • {error}")

            return [types.TextContent(type="text", text="\n".join(error_lines))]

    except Exception as e:
        return [
            types.TextContent(
                type="text",
                text=f"Error during rollback: {e!s}",
            )
        ]
