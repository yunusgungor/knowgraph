"""API versioning support for KnowGraph.

This module provides comprehensive API versioning capabilities including:
- Semantic version parsing and comparison
- Version negotiation and compatibility checks
- Deprecation tracking and warnings
- Version-specific feature flags
- Backward compatibility utilities
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class VersionStatus(Enum):
    """Status of an API version."""

    DEVELOPMENT = "development"  # In active development, not stable
    STABLE = "stable"  # Production-ready, fully supported
    DEPRECATED = "deprecated"  # Still works but will be removed
    SUNSET = "sunset"  # No longer supported, will fail


@dataclass
class Version:
    """Semantic version representation.

    Follows semantic versioning: MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
    - MAJOR: Breaking changes
    - MINOR: New features, backward compatible
    - PATCH: Bug fixes, backward compatible
    """

    major: int
    minor: int
    patch: int
    prerelease: str | None = None
    build: str | None = None

    def __str__(self) -> str:
        """Format version as string."""
        version_str = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version_str += f"-{self.prerelease}"
        if self.build:
            version_str += f"+{self.build}"
        return version_str

    def __repr__(self) -> str:
        """Representation string."""
        return f"Version('{self}')"

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if not isinstance(other, Version):
            return NotImplemented
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
            and self.prerelease == other.prerelease
        )

    def __lt__(self, other: Version) -> bool:
        """Check if this version is less than other."""
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        if self.patch != other.patch:
            return self.patch < other.patch

        # Handle prerelease versions (1.0.0-alpha < 1.0.0)
        if self.prerelease and not other.prerelease:
            return True
        if not self.prerelease and other.prerelease:
            return False
        if self.prerelease and other.prerelease:
            return self.prerelease < other.prerelease

        return False

    def __le__(self, other: Version) -> bool:
        """Check if this version is less than or equal to other."""
        return self == other or self < other

    def __gt__(self, other: Version) -> bool:
        """Check if this version is greater than other."""
        return not self <= other

    def __ge__(self, other: Version) -> bool:
        """Check if this version is greater than or equal to other."""
        return not self < other

    @classmethod
    def parse(cls, version_str: str) -> Version:
        """Parse version string into Version object.

        Args:
        ----
            version_str: Version string (e.g., "1.2.3", "2.0.0-beta", "1.0.0+build123")

        Returns:
        -------
            Parsed Version object

        Raises:
        ------
            ValueError: If version string is invalid
        """
        # Regex for semantic versioning
        pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.-]+))?(?:\+([a-zA-Z0-9.-]+))?$"
        match = re.match(pattern, version_str.strip())

        if not match:
            raise ValueError(f"Invalid version string: {version_str}")

        major, minor, patch, prerelease, build = match.groups()
        return cls(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=prerelease,
            build=build,
        )

    def is_compatible_with(self, other: Version) -> bool:
        """Check if this version is compatible with another version.

        Compatibility rules:
        - Same major version (e.g., 1.x.x is compatible with 1.y.z)
        - Minor/patch versions are backward compatible within same major
        - Different major versions are incompatible

        Args:
        ----
            other: Version to check compatibility with

        Returns:
        -------
            True if versions are compatible
        """
        return self.major == other.major


@dataclass
class VersionInfo:
    """Information about an API version."""

    version: Version
    status: VersionStatus
    release_date: datetime
    deprecation_date: datetime | None = None
    sunset_date: datetime | None = None
    features: list[str] = field(default_factory=list)
    breaking_changes: list[str] = field(default_factory=list)
    migration_guide: str | None = None

    def is_active(self) -> bool:
        """Check if version is still active (not sunset)."""
        return self.status != VersionStatus.SUNSET

    def is_supported(self) -> bool:
        """Check if version is currently supported."""
        return self.status in (VersionStatus.STABLE, VersionStatus.DEPRECATED)

    def days_until_sunset(self) -> int | None:
        """Calculate days until version is sunset."""
        if not self.sunset_date:
            return None
        delta = self.sunset_date - datetime.now()
        return max(0, delta.days)

    def get_deprecation_warning(self) -> str | None:
        """Get deprecation warning message if version is deprecated."""
        if self.status != VersionStatus.DEPRECATED:
            return None

        warning = f"API version {self.version} is deprecated"
        if self.sunset_date:
            days = self.days_until_sunset()
            if days is not None:
                warning += f" and will be removed in {days} days"
        if self.migration_guide:
            warning += f". See migration guide: {self.migration_guide}"

        return warning


class VersionRegistry:
    """Registry of all API versions and their metadata."""

    def __init__(self) -> None:
        """Initialize version registry."""
        self._versions: dict[str, VersionInfo] = {}
        self._current_version: Version | None = None

    def register(
        self,
        version: Version | str,
        status: VersionStatus,
        release_date: datetime,
        deprecation_date: datetime | None = None,
        sunset_date: datetime | None = None,
        features: list[str] | None = None,
        breaking_changes: list[str] | None = None,
        migration_guide: str | None = None,
    ) -> None:
        """Register a new API version.

        Args:
        ----
            version: Version object or string
            status: Version status
            release_date: When version was released
            deprecation_date: When version was deprecated (if applicable)
            sunset_date: When version will be removed (if applicable)
            features: List of new features in this version
            breaking_changes: List of breaking changes
            migration_guide: URL or path to migration documentation
        """
        if isinstance(version, str):
            version = Version.parse(version)

        version_info = VersionInfo(
            version=version,
            status=status,
            release_date=release_date,
            deprecation_date=deprecation_date,
            sunset_date=sunset_date,
            features=features or [],
            breaking_changes=breaking_changes or [],
            migration_guide=migration_guide,
        )

        self._versions[str(version)] = version_info

        # Set as current if it's the first stable version or newer stable version
        if status == VersionStatus.STABLE and (
            not self._current_version
            or version > self._current_version
        ):
            self._current_version = version

    def get_version_info(self, version: Version | str) -> VersionInfo | None:
        """Get information about a specific version."""
        if isinstance(version, Version):
            version = str(version)
        return self._versions.get(version)

    def get_current_version(self) -> Version | None:
        """Get the current stable version."""
        return self._current_version

    def get_supported_versions(self) -> list[Version]:
        """Get list of all supported versions."""
        return [
            info.version
            for info in self._versions.values()
            if info.is_supported()
        ]

    def negotiate_version(
        self,
        requested: Version | str | None,
        minimum: Version | str | None = None,
    ) -> Version:
        """Negotiate the best version to use.

        Args:
        ----
            requested: Version requested by client (None = use current)
            minimum: Minimum acceptable version

        Returns:
        -------
            Version to use

        Raises:
        ------
            ValueError: If requested version is not supported or incompatible
        """
        if isinstance(requested, str):
            requested = Version.parse(requested)
        if isinstance(minimum, str):
            minimum = Version.parse(minimum)

        # Use current version if not specified
        if requested is None:
            if not self._current_version:
                raise ValueError("No current version available")
            return self._current_version

        # Check if requested version exists and is supported
        version_info = self.get_version_info(requested)
        if not version_info:
            raise ValueError(f"Version {requested} not found")

        if not version_info.is_supported():
            raise ValueError(
                f"Version {requested} is not supported (status: {version_info.status.value})"
            )

        # Check minimum version constraint
        if minimum and requested < minimum:
            raise ValueError(
                f"Version {requested} is below minimum required version {minimum}"
            )

        # Issue deprecation warning if needed
        if warning_msg := version_info.get_deprecation_warning():
            warnings.warn(warning_msg, DeprecationWarning, stacklevel=2)

        return requested

    def get_migration_path(
        self, from_version: Version | str, to_version: Version | str
    ) -> list[VersionInfo]:
        """Get migration path between two versions.

        Returns list of versions that need to be traversed to migrate.

        Args:
        ----
            from_version: Starting version
            to_version: Target version

        Returns:
        -------
            List of versions in migration path (including target)
        """
        if isinstance(from_version, str):
            from_version = Version.parse(from_version)
        if isinstance(to_version, str):
            to_version = Version.parse(to_version)

        # Get all versions between from and to
        path = []
        for version_str, info in sorted(
            self._versions.items(),
            key=lambda x: x[1].version
        ):
            if from_version < info.version <= to_version:
                path.append(info)

        return path


# Global version registry
_registry = VersionRegistry()


def get_version_registry() -> VersionRegistry:
    """Get the global version registry."""
    return _registry


def register_version(
    version: Version | str,
    status: VersionStatus,
    release_date: datetime,
    **kwargs: Any,
) -> None:
    """Register a new API version in the global registry."""
    _registry.register(version, status, release_date, **kwargs)


def get_current_version() -> Version | None:
    """Get the current API version."""
    return _registry.get_current_version()


def negotiate_version(
    requested: Version | str | None,
    minimum: Version | str | None = None,
) -> Version:
    """Negotiate version using the global registry."""
    return _registry.negotiate_version(requested, minimum)
