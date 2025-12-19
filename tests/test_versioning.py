"""Tests for API versioning system."""

import warnings
from datetime import datetime, timedelta

import pytest

from knowgraph.shared.versioning import (
    Version,
    VersionInfo,
    VersionRegistry,
    VersionStatus,
    get_current_version,
    negotiate_version,
    register_version,
)


class TestVersion:
    """Tests for Version class."""

    def test_version_parsing(self):
        """Test parsing version strings."""
        v = Version.parse("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3
        assert v.prerelease is None
        assert v.build is None

    def test_version_with_prerelease(self):
        """Test parsing version with prerelease."""
        v = Version.parse("2.0.0-beta.1")
        assert v.major == 2
        assert v.minor == 0
        assert v.patch == 0
        assert v.prerelease == "beta.1"
        assert v.build is None

    def test_version_with_build(self):
        """Test parsing version with build metadata."""
        v = Version.parse("1.0.0+build.123")
        assert v.major == 1
        assert v.minor == 0
        assert v.patch == 0
        assert v.prerelease is None
        assert v.build == "build.123"

    def test_version_full(self):
        """Test parsing full version string."""
        v = Version.parse("3.1.4-rc.2+build.456")
        assert v.major == 3
        assert v.minor == 1
        assert v.patch == 4
        assert v.prerelease == "rc.2"
        assert v.build == "build.456"

    def test_invalid_version(self):
        """Test parsing invalid version strings."""
        with pytest.raises(ValueError, match="Invalid version string"):
            Version.parse("invalid")

        with pytest.raises(ValueError, match="Invalid version string"):
            Version.parse("1.2")

        with pytest.raises(ValueError, match="Invalid version string"):
            Version.parse("a.b.c")

    def test_version_string_format(self):
        """Test version string formatting."""
        v = Version(1, 2, 3)
        assert str(v) == "1.2.3"

        v = Version(2, 0, 0, prerelease="beta")
        assert str(v) == "2.0.0-beta"

        v = Version(1, 0, 0, build="build123")
        assert str(v) == "1.0.0+build123"

        v = Version(3, 1, 4, prerelease="rc.1", build="build456")
        assert str(v) == "3.1.4-rc.1+build456"

    def test_version_equality(self):
        """Test version equality comparison."""
        v1 = Version(1, 2, 3)
        v2 = Version(1, 2, 3)
        v3 = Version(1, 2, 4)

        assert v1 == v2
        assert v1 != v3

    def test_version_comparison(self):
        """Test version comparison operators."""
        v1 = Version(1, 0, 0)
        v2 = Version(1, 1, 0)
        v3 = Version(2, 0, 0)

        # Less than
        assert v1 < v2
        assert v2 < v3
        assert v1 < v3

        # Less than or equal
        assert v1 <= v2
        assert v1 <= v1

        # Greater than
        assert v3 > v2
        assert v2 > v1

        # Greater than or equal
        assert v3 >= v2
        assert v1 >= v1

    def test_prerelease_comparison(self):
        """Test that prerelease versions are less than release versions."""
        v1 = Version(1, 0, 0, prerelease="alpha")
        v2 = Version(1, 0, 0, prerelease="beta")
        v3 = Version(1, 0, 0)

        assert v1 < v3  # alpha < release
        assert v2 < v3  # beta < release
        assert v1 < v2  # alpha < beta

    def test_version_compatibility(self):
        """Test version compatibility checks."""
        v1_0 = Version(1, 0, 0)
        v1_5 = Version(1, 5, 0)
        v2_0 = Version(2, 0, 0)

        # Same major version = compatible
        assert v1_0.is_compatible_with(v1_5)
        assert v1_5.is_compatible_with(v1_0)

        # Different major version = incompatible
        assert not v1_0.is_compatible_with(v2_0)
        assert not v2_0.is_compatible_with(v1_0)


class TestVersionInfo:
    """Tests for VersionInfo class."""

    def test_version_info_creation(self):
        """Test creating version info."""
        now = datetime.now()
        info = VersionInfo(
            version=Version(1, 0, 0),
            status=VersionStatus.STABLE,
            release_date=now,
        )

        assert info.version == Version(1, 0, 0)
        assert info.status == VersionStatus.STABLE
        assert info.release_date == now

    def test_is_active(self):
        """Test checking if version is active."""
        now = datetime.now()

        stable = VersionInfo(
            version=Version(1, 0, 0),
            status=VersionStatus.STABLE,
            release_date=now,
        )
        assert stable.is_active()

        sunset = VersionInfo(
            version=Version(0, 5, 0),
            status=VersionStatus.SUNSET,
            release_date=now - timedelta(days=365),
        )
        assert not sunset.is_active()

    def test_is_supported(self):
        """Test checking if version is supported."""
        now = datetime.now()

        stable = VersionInfo(
            version=Version(1, 0, 0),
            status=VersionStatus.STABLE,
            release_date=now,
        )
        assert stable.is_supported()

        deprecated = VersionInfo(
            version=Version(0, 9, 0),
            status=VersionStatus.DEPRECATED,
            release_date=now - timedelta(days=90),
        )
        assert deprecated.is_supported()

        dev = VersionInfo(
            version=Version(2, 0, 0),
            status=VersionStatus.DEVELOPMENT,
            release_date=now,
        )
        assert not dev.is_supported()

    def test_days_until_sunset(self):
        """Test calculating days until sunset."""
        now = datetime.now()
        future = now + timedelta(days=90)

        info = VersionInfo(
            version=Version(1, 0, 0),
            status=VersionStatus.DEPRECATED,
            release_date=now,
            sunset_date=future,
        )

        days = info.days_until_sunset()
        assert days is not None
        assert 89 <= days <= 90  # Account for timing

    def test_deprecation_warning(self):
        """Test getting deprecation warning message."""
        now = datetime.now()

        # Not deprecated - no warning
        stable = VersionInfo(
            version=Version(1, 0, 0),
            status=VersionStatus.STABLE,
            release_date=now,
        )
        assert stable.get_deprecation_warning() is None

        # Deprecated without sunset date
        deprecated = VersionInfo(
            version=Version(0, 9, 0),
            status=VersionStatus.DEPRECATED,
            release_date=now - timedelta(days=90),
        )
        warning = deprecated.get_deprecation_warning()
        assert warning is not None
        assert "0.9.0 is deprecated" in warning

        # Deprecated with sunset date
        future = now + timedelta(days=30)
        deprecated_with_sunset = VersionInfo(
            version=Version(0, 8, 0),
            status=VersionStatus.DEPRECATED,
            release_date=now - timedelta(days=180),
            sunset_date=future,
            migration_guide="https://docs.example.com/migration",
        )
        warning = deprecated_with_sunset.get_deprecation_warning()
        assert warning is not None
        assert "0.8.0 is deprecated" in warning
        assert "30 days" in warning or "29 days" in warning  # Account for timing
        assert "migration guide" in warning


class TestVersionRegistry:
    """Tests for VersionRegistry class."""

    def test_register_version(self):
        """Test registering versions."""
        registry = VersionRegistry()
        now = datetime.now()

        registry.register(
            version="1.0.0",
            status=VersionStatus.STABLE,
            release_date=now,
        )

        info = registry.get_version_info("1.0.0")
        assert info is not None
        assert info.version == Version(1, 0, 0)
        assert info.status == VersionStatus.STABLE

    def test_get_current_version(self):
        """Test getting current stable version."""
        registry = VersionRegistry()
        now = datetime.now()

        # No versions yet
        assert registry.get_current_version() is None

        # Register first stable version
        registry.register("1.0.0", VersionStatus.STABLE, now)
        assert registry.get_current_version() == Version(1, 0, 0)

        # Register newer stable version
        registry.register("1.1.0", VersionStatus.STABLE, now)
        assert registry.get_current_version() == Version(1, 1, 0)

        # Register development version (should not become current)
        registry.register("2.0.0", VersionStatus.DEVELOPMENT, now)
        assert registry.get_current_version() == Version(1, 1, 0)

    def test_get_supported_versions(self):
        """Test getting list of supported versions."""
        registry = VersionRegistry()
        now = datetime.now()

        registry.register("0.9.0", VersionStatus.DEPRECATED, now - timedelta(days=180))
        registry.register("1.0.0", VersionStatus.STABLE, now - timedelta(days=90))
        registry.register("1.1.0", VersionStatus.STABLE, now)
        registry.register("2.0.0", VersionStatus.DEVELOPMENT, now)
        registry.register("0.5.0", VersionStatus.SUNSET, now - timedelta(days=365))

        supported = registry.get_supported_versions()
        assert len(supported) == 3
        assert Version(0, 9, 0) in supported
        assert Version(1, 0, 0) in supported
        assert Version(1, 1, 0) in supported
        assert Version(2, 0, 0) not in supported  # Development
        assert Version(0, 5, 0) not in supported  # Sunset

    def test_negotiate_version_default(self):
        """Test version negotiation with default (current) version."""
        registry = VersionRegistry()
        now = datetime.now()

        registry.register("1.0.0", VersionStatus.STABLE, now)

        # Request None should return current version
        version = registry.negotiate_version(None)
        assert version == Version(1, 0, 0)

    def test_negotiate_version_specific(self):
        """Test version negotiation with specific version."""
        registry = VersionRegistry()
        now = datetime.now()

        registry.register("1.0.0", VersionStatus.STABLE, now - timedelta(days=90))
        registry.register("1.1.0", VersionStatus.STABLE, now)

        # Request specific version
        version = registry.negotiate_version("1.0.0")
        assert version == Version(1, 0, 0)

    def test_negotiate_version_not_found(self):
        """Test version negotiation with non-existent version."""
        registry = VersionRegistry()
        now = datetime.now()

        registry.register("1.0.0", VersionStatus.STABLE, now)

        with pytest.raises(ValueError, match="not found"):
            registry.negotiate_version("2.0.0")

    def test_negotiate_version_not_supported(self):
        """Test version negotiation with unsupported version."""
        registry = VersionRegistry()
        now = datetime.now()

        registry.register("0.5.0", VersionStatus.SUNSET, now - timedelta(days=365))
        registry.register("1.0.0", VersionStatus.STABLE, now)

        with pytest.raises(ValueError, match="not supported"):
            registry.negotiate_version("0.5.0")

    def test_negotiate_version_minimum(self):
        """Test version negotiation with minimum version constraint."""
        registry = VersionRegistry()
        now = datetime.now()

        registry.register("1.0.0", VersionStatus.STABLE, now - timedelta(days=90))
        registry.register("1.1.0", VersionStatus.STABLE, now)

        # Request version that meets minimum
        version = registry.negotiate_version("1.1.0", minimum="1.0.0")
        assert version == Version(1, 1, 0)

        # Request version below minimum
        with pytest.raises(ValueError, match="below minimum"):
            registry.negotiate_version("1.0.0", minimum="1.1.0")

    def test_negotiate_version_deprecated_warning(self):
        """Test that deprecated versions trigger warnings."""
        registry = VersionRegistry()
        now = datetime.now()

        registry.register(
            "0.9.0",
            VersionStatus.DEPRECATED,
            now - timedelta(days=180),
            sunset_date=now + timedelta(days=30),
        )
        registry.register("1.0.0", VersionStatus.STABLE, now)

        # Negotiating deprecated version should warn
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            registry.negotiate_version("0.9.0")
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "0.9.0 is deprecated" in str(w[0].message)

    def test_get_migration_path(self):
        """Test getting migration path between versions."""
        registry = VersionRegistry()
        now = datetime.now()

        registry.register("1.0.0", VersionStatus.STABLE, now - timedelta(days=180))
        registry.register("1.1.0", VersionStatus.STABLE, now - timedelta(days=120))
        registry.register("1.2.0", VersionStatus.STABLE, now - timedelta(days=60))
        registry.register("2.0.0", VersionStatus.STABLE, now)

        # Get migration path from 1.0.0 to 2.0.0
        path = registry.get_migration_path("1.0.0", "2.0.0")
        assert len(path) == 3
        assert path[0].version == Version(1, 1, 0)
        assert path[1].version == Version(1, 2, 0)
        assert path[2].version == Version(2, 0, 0)

        # Get migration path for single version jump
        path = registry.get_migration_path("1.1.0", "1.2.0")
        assert len(path) == 1
        assert path[0].version == Version(1, 2, 0)


class TestGlobalRegistry:
    """Tests for global registry functions."""

    def test_register_and_get_version(self):
        """Test global register and get functions."""
        now = datetime.now()

        # Clear registry by creating new one
        from knowgraph.shared import versioning
        versioning._registry = VersionRegistry()

        register_version("1.0.0", VersionStatus.STABLE, now)

        current = get_current_version()
        assert current == Version(1, 0, 0)

    def test_negotiate_version_global(self):
        """Test global negotiate_version function."""
        now = datetime.now()

        # Clear registry
        from knowgraph.shared import versioning
        versioning._registry = VersionRegistry()

        register_version("1.0.0", VersionStatus.STABLE, now)

        version = negotiate_version("1.0.0")
        assert version == Version(1, 0, 0)


class TestVersionOrdering:
    """Tests for version ordering and sorting."""

    def test_version_sorting(self):
        """Test sorting versions."""
        versions = [
            Version(2, 0, 0),
            Version(1, 0, 0),
            Version(1, 2, 0),
            Version(1, 1, 0),
            Version(1, 0, 1),
        ]

        sorted_versions = sorted(versions)
        assert sorted_versions[0] == Version(1, 0, 0)
        assert sorted_versions[1] == Version(1, 0, 1)
        assert sorted_versions[2] == Version(1, 1, 0)
        assert sorted_versions[3] == Version(1, 2, 0)
        assert sorted_versions[4] == Version(2, 0, 0)

    def test_prerelease_sorting(self):
        """Test sorting with prerelease versions."""
        versions = [
            Version(1, 0, 0),
            Version(1, 0, 0, prerelease="beta"),
            Version(1, 0, 0, prerelease="alpha"),
            Version(1, 0, 0, prerelease="rc"),
        ]

        sorted_versions = sorted(versions)
        # Prereleases come before release
        assert sorted_versions[0] == Version(1, 0, 0, prerelease="alpha")
        assert sorted_versions[1] == Version(1, 0, 0, prerelease="beta")
        assert sorted_versions[2] == Version(1, 0, 0, prerelease="rc")
        assert sorted_versions[3] == Version(1, 0, 0)
