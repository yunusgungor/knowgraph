"""Version comparison and diff engine for knowledge graphs."""

import logging
from dataclasses import dataclass, field

from knowgraph.infrastructure.storage.version_history import (
    FileChangeSummary,
    VersionSnapshot,
)

logger = logging.getLogger(__name__)


@dataclass
class VersionDiff:
    """Diff between two versions."""

    from_version: str
    to_version: str
    timestamp_diff: int
    node_count_diff: int
    edge_count_diff: int
    file_changes: FileChangeSummary
    significant_changes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "from_version": self.from_version,
            "to_version": self.to_version,
            "timestamp_diff": self.timestamp_diff,
            "node_count_diff": self.node_count_diff,
            "edge_count_diff": self.edge_count_diff,
            "file_changes": self.file_changes.to_dict(),
            "significant_changes": self.significant_changes,
        }


class VersionDiffEngine:
    """Generate diffs between versions."""

    def diff_versions(self, v1: VersionSnapshot, v2: VersionSnapshot) -> VersionDiff:
        """Generate diff between two versions.

        Args:
            v1: First version (older)
            v2: Second version (newer)

        Returns:
            Version diff object
        """
        # Calculate timestamp difference
        timestamp_diff = v2.timestamp - v1.timestamp

        # Calculate count differences
        node_count_diff = v2.node_count - v1.node_count
        edge_count_diff = v2.edge_count - v1.edge_count

        # Use file changes from v2 (which was calculated against v1)
        file_changes = v2.file_changes

        # Generate significant changes list
        significant_changes = self._generate_significant_changes(
            v1, v2, node_count_diff, edge_count_diff, file_changes
        )

        return VersionDiff(
            from_version=v1.version_id,
            to_version=v2.version_id,
            timestamp_diff=timestamp_diff,
            node_count_diff=node_count_diff,
            edge_count_diff=edge_count_diff,
            file_changes=file_changes,
            significant_changes=significant_changes,
        )

    def _generate_significant_changes(
        self,
        v1: VersionSnapshot,
        v2: VersionSnapshot,
        node_diff: int,
        edge_diff: int,
        file_changes: FileChangeSummary,
    ) -> list[str]:
        """Generate human-readable list of significant changes.

        Args:
            v1: First version
            v2: Second version
            node_diff: Node count difference
            edge_diff: Edge count difference
            file_changes: File change summary

        Returns:
            List of significant change descriptions
        """
        changes = []

        # Node changes
        if node_diff > 0:
            changes.append(f"Added {node_diff:,} nodes")
        elif node_diff < 0:
            changes.append(f"Removed {abs(node_diff):,} nodes")

        # Edge changes
        if edge_diff > 0:
            changes.append(f"Added {edge_diff:,} edges")
        elif edge_diff < 0:
            changes.append(f"Removed {abs(edge_diff):,} edges")

        # File changes
        if file_changes.added:
            changes.append(f"Added {len(file_changes.added)} new files")
        if file_changes.modified:
            changes.append(f"Modified {len(file_changes.modified)} files")
        if file_changes.deleted:
            changes.append(f"Deleted {len(file_changes.deleted)} files")

        # Time-based changes
        hours_diff = (v2.timestamp - v1.timestamp) / 3600
        if hours_diff < 1:
            changes.append(f"Updated {int(hours_diff * 60)} minutes ago")
        elif hours_diff < 24:
            changes.append(f"Updated {int(hours_diff)} hours ago")
        else:
            changes.append(f"Updated {int(hours_diff / 24)} days ago")

        return changes

    def format_diff_report(self, diff: VersionDiff) -> str:
        """Format diff as human-readable report.

        Args:
            diff: Version diff object

        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 80)
        lines.append(f"VERSION DIFF: {diff.from_version} → {diff.to_version}")
        lines.append("=" * 80)

        # Time difference
        hours = diff.timestamp_diff / 3600
        if hours < 1:
            time_str = f"{int(hours * 60)} minutes"
        elif hours < 24:
            time_str = f"{int(hours)} hours"
        else:
            time_str = f"{int(hours / 24)} days"
        lines.append(f"\nTime difference: {time_str}")

        # Graph statistics
        lines.append("\nGraph Statistics:")
        lines.append(f"  Nodes:  {diff.node_count_diff:+,}")
        lines.append(f"  Edges:  {diff.edge_count_diff:+,}")

        # File changes
        lines.append("\nFile Changes:")
        if diff.file_changes.added:
            lines.append(f"  Added:    {len(diff.file_changes.added)} files")
            for f in sorted(diff.file_changes.added)[:5]:  # Show first 5
                lines.append(f"    + {f}")
            if len(diff.file_changes.added) > 5:
                lines.append(f"    ... and {len(diff.file_changes.added) - 5} more")

        if diff.file_changes.modified:
            lines.append(f"  Modified: {len(diff.file_changes.modified)} files")
            for f in sorted(diff.file_changes.modified)[:5]:
                lines.append(f"    M {f}")
            if len(diff.file_changes.modified) > 5:
                lines.append(f"    ... and {len(diff.file_changes.modified) - 5} more")

        if diff.file_changes.deleted:
            lines.append(f"  Deleted:  {len(diff.file_changes.deleted)} files")
            for f in sorted(diff.file_changes.deleted)[:5]:
                lines.append(f"    - {f}")
            if len(diff.file_changes.deleted) > 5:
                lines.append(f"    ... and {len(diff.file_changes.deleted) - 5} more")

        # Summary
        lines.append("\nSignificant Changes:")
        for change in diff.significant_changes:
            lines.append(f"  • {change}")

        lines.append("=" * 80)

        return "\n".join(lines)
