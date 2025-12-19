"""CLI commands for version management."""

from pathlib import Path

import click

from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
from knowgraph.infrastructure.storage.version_diff import VersionDiffEngine
from knowgraph.infrastructure.storage.version_history import VersionHistoryManager


@click.group()
def version_commands():
    """Version control commands."""


@click.command(name="versions")
@click.option(
    "--graph-store",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_GRAPH_STORE_PATH,
    help="Graph store directory path",
)
@click.option(
    "--limit",
    type=int,
    default=50,
    help="Maximum number of versions to show",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Show detailed information",
)
def list_versions(graph_store: Path, limit: int, verbose: bool):
    """List all versions in the knowledge graph."""
    try:
        version_mgr = VersionHistoryManager(graph_store)
        versions = version_mgr.list_versions(limit=limit)

        if not versions:
            click.echo("No versions found.")
            return

        click.echo(f"\n{'='*80}")
        click.echo(f"VERSION HISTORY ({len(versions)} versions)")
        click.echo(f"{'='*80}\n")

        for v in versions:
            click.echo(f"  {v.version_id:<8} {v.created_at_iso:<25}")
            click.echo(
                f"           Nodes: {v.node_count:>6,}  Edges: {v.edge_count:>6,}  Files: {v.file_count:>4}"
            )

            if verbose and v.file_changes.total_changes > 0:
                fc = v.file_changes
                click.echo(
                    f"           Changes: +{len(fc.added)} ~{len(fc.modified)} -{len(fc.deleted)}"
                )

            if verbose and v.metadata:
                click.echo(f"           Metadata: {v.metadata}")

            click.echo()

        click.echo(f"{'='*80}\n")

    except Exception as e:
        click.echo(f"Error listing versions: {e}", err=True)
        raise click.Abort()


@click.command(name="show")
@click.argument("version_id")
@click.option(
    "--graph-store",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_GRAPH_STORE_PATH,
    help="Graph store directory path",
)
def show_version(version_id: str, graph_store: Path):
    """Show detailed information about a specific version."""
    try:
        version_mgr = VersionHistoryManager(graph_store)
        version = version_mgr.get_version(version_id)

        if not version:
            click.echo(f"Version '{version_id}' not found.", err=True)
            raise click.Abort()

        click.echo(f"\n{'='*80}")
        click.echo(f"VERSION {version.version_id}")
        click.echo(f"{'='*80}\n")

        click.echo(f"Created:  {version.created_at_iso}")
        click.echo(f"Hash:     {version.manifest_hash}")
        click.echo()

        click.echo("Graph Statistics:")
        click.echo(f"  Nodes:    {version.node_count:>8,}")
        click.echo(f"  Edges:    {version.edge_count:>8,}")
        click.echo(f"  Files:    {version.file_count:>8,}")
        click.echo()

        fc = version.file_changes
        if fc.total_changes > 0:
            click.echo("File Changes:")
            if fc.added:
                click.echo(f"  Added:    {len(fc.added):>8,} files")
                for f in sorted(fc.added)[:10]:
                    click.echo(f"    + {f}")
                if len(fc.added) > 10:
                    click.echo(f"    ... and {len(fc.added) - 10} more")

            if fc.modified:
                click.echo(f"  Modified: {len(fc.modified):>8,} files")
                for f in sorted(fc.modified)[:10]:
                    click.echo(f"    M {f}")
                if len(fc.modified) > 10:
                    click.echo(f"    ... and {len(fc.modified) - 10} more")

            if fc.deleted:
                click.echo(f"  Deleted:  {len(fc.deleted):>8,} files")
                for f in sorted(fc.deleted)[:10]:
                    click.echo(f"    - {f}")
                if len(fc.deleted) > 10:
                    click.echo(f"    ... and {len(fc.deleted) - 10} more")

        if version.metadata:
            click.echo()
            click.echo("Metadata:")
            for key, value in version.metadata.items():
                click.echo(f"  {key}: {value}")

        click.echo(f"\n{'='*80}\n")

    except Exception as e:
        click.echo(f"Error showing version: {e}", err=True)
        raise click.Abort()


@click.command(name="diff")
@click.argument("version1")
@click.argument("version2")
@click.option(
    "--graph-store",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_GRAPH_STORE_PATH,
    help="Graph store directory path",
)
def diff_versions(version1: str, version2: str, graph_store: Path):
    """Compare two versions and show differences."""
    try:
        version_mgr = VersionHistoryManager(graph_store)

        v1 = version_mgr.get_version(version1)
        if not v1:
            click.echo(f"Version '{version1}' not found.", err=True)
            raise click.Abort()

        v2 = version_mgr.get_version(version2)
        if not v2:
            click.echo(f"Version '{version2}' not found.", err=True)
            raise click.Abort()

        # Generate and display diff
        diff_engine = VersionDiffEngine()
        diff = diff_engine.diff_versions(v1, v2)
        report = diff_engine.format_diff_report(diff)

        click.echo("\n" + report + "\n")

    except Exception as e:
        click.echo(f"Error diffing versions: {e}", err=True)
        raise click.Abort()


@click.command(name="rollback")
@click.argument("version_id")
@click.option(
    "--graph-store",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_GRAPH_STORE_PATH,
    help="Graph store directory path",
)
@click.option(
    "--no-backup",
    is_flag=True,
    help="Skip creating backup before rollback",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force rollback without validation checks",
)
def rollback_version(version_id: str, graph_store: Path, no_backup: bool, force: bool):
    """Rollback to a previous version (manifest metadata only)."""
    from knowgraph.infrastructure.storage.version_rollback import RollbackManager

    try:
        # Confirmation prompt
        if not force:
            click.confirm(
                f"⚠️  This will rollback manifest to {version_id}. "
                "Note: This is metadata-only. "
                "You'll need to re-index to restore files. Continue?",
                abort=True,
            )

        rollback_mgr = RollbackManager(graph_store)
        result = rollback_mgr.rollback_to_version(
            target_version_id=version_id,
            create_backup=not no_backup,
            force=force,
        )

        if result.success:
            click.echo(f"\n{'='*80}")
            click.echo(f"✅ {result.message}")
            click.echo(f"{'='*80}\n")

            click.echo(f"Rolled back: {result.from_version} → {result.to_version}")

            if result.backup_path:
                click.echo(f"Backup created: {result.backup_path}")

            if result.errors:
                click.echo("\n⚠️  Warnings:")
                for error in result.errors:
                    click.echo(f"  • {error}")

            click.echo("\n💡 Next steps:")
            click.echo("  1. Review the rollback")
            click.echo("  2. Run 'knowgraph index' to restore files if needed")

        else:
            click.echo(f"\n❌ Rollback failed: {result.message}", err=True)
            if result.errors:
                for error in result.errors:
                    click.echo(f"  • {error}", err=True)
            raise click.Abort()

    except Exception as e:
        click.echo(f"Error during rollback: {e}", err=True)
        raise click.Abort()


# Register commands
version_commands.add_command(list_versions)
version_commands.add_command(show_version)
version_commands.add_command(diff_versions)
version_commands.add_command(rollback_version)
