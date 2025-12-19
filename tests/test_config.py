"""Comprehensive tests for configuration system."""

from pathlib import Path

import pytest

from knowgraph.config import (
    KnowGraphSettings,
    MemorySettings,
    PerformanceSettings,
    QuerySettings,
    get_settings,
)


class TestDefaultSettings:
    """Test default configuration values."""

    def test_performance_defaults(self):
        """Test performance settings have correct defaults."""
        perf = PerformanceSettings()
        assert perf.max_workers == 10
        assert perf.cache_size == 1000
        assert perf.batch_size == 10

    def test_memory_defaults(self):
        """Test memory settings have correct defaults."""
        mem = MemorySettings()
        assert mem.warning_threshold_mb == 500
        assert mem.critical_threshold_mb == 1000
        assert mem.auto_gc is True

    def test_query_defaults(self):
        """Test query settings have correct defaults."""
        query = QuerySettings()
        assert query.top_k == 20
        assert query.max_hops == 4
        assert query.enable_query_expansion is False
        assert query.timeout_seconds == 30.0

    def test_main_settings_defaults(self):
        """Test main settings have correct defaults."""
        settings = KnowGraphSettings()
        assert settings.log_level == "INFO"
        assert settings.graph_store_path == Path("./graphstore")


class TestEnvironmentOverrides:
    """Test environment variable overrides."""

    def test_env_var_override_performance(self, monkeypatch):
        """Test environment variable overrides performance settings."""
        monkeypatch.setenv("KNOWGRAPH_PERF_MAX_WORKERS", "20")
        settings = KnowGraphSettings()
        assert settings.performance.max_workers == 20

    def test_multiple_env_overrides(self, monkeypatch):
        """Test multiple environment variable overrides."""
        monkeypatch.setenv("KNOWGRAPH_QUERY_TOP_K", "50")
        monkeypatch.setenv("KNOWGRAPH_QUERY_MAX_HOPS", "6")
        settings = KnowGraphSettings()
        assert settings.query.top_k == 50
        assert settings.query.max_hops == 6

    def test_memory_thresholds_override(self, monkeypatch):
        """Test memory threshold overrides."""
        monkeypatch.setenv("KNOWGRAPH_MEMORY_WARNING_THRESHOLD_MB", "300")
        monkeypatch.setenv("KNOWGRAPH_MEMORY_CRITICAL_THRESHOLD_MB", "800")
        settings = KnowGraphSettings()
        assert settings.memory.warning_threshold_mb == 300
        assert settings.memory.critical_threshold_mb == 800


class TestConfigValidation:
    """Test configuration validation."""

    def test_invalid_workers_count_too_low(self):
        """Test validation fails for workers count < 1."""
        with pytest.raises(ValueError):
            PerformanceSettings(max_workers=0)

    def test_invalid_workers_count_too_high(self):
        """Test validation fails for workers count > 50."""
        with pytest.raises(ValueError):
            PerformanceSettings(max_workers=100)

    def test_invalid_cache_size(self):
        """Test validation fails for invalid cache size."""
        with pytest.raises(ValueError):
            PerformanceSettings(cache_size=50)  # Below minimum of 100

    def test_invalid_log_level(self, monkeypatch):
        """Test validation fails for invalid log level."""
        monkeypatch.setenv("KNOWGRAPH_LOG_LEVEL", "INVALID")
        with pytest.raises(ValueError):
            KnowGraphSettings()


class TestSettingsCaching:
    """Test settings singleton behavior."""

    def test_get_settings_returns_same_instance(self):
        """Test get_settings() returns cached instance."""
        # Clear cache first
        get_settings.cache_clear()

        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_settings_cached_across_calls(self):
        """Test settings remain cached."""
        get_settings.cache_clear()

        s1 = get_settings()
        # Make multiple calls
        for _ in range(10):
            s = get_settings()
            assert s is s1


class TestConfigIntegration:
    """Integration tests for config system."""

    def test_config_used_by_memory_profiler(self):
        """Test config is used by memory profiler."""
        from knowgraph.shared.memory_profiler import (
            CRITICAL_THRESHOLD_MB,
            WARNING_THRESHOLD_MB,
        )

        # Should match default config
        assert WARNING_THRESHOLD_MB == 500
        assert CRITICAL_THRESHOLD_MB == 1000

    def test_sparse_embedder_cache_documented(self):
        """Test sparse embedder has cache size documented."""
        from knowgraph.infrastructure.embedding import sparse_embedder

        # Check that documentation mentions config
        source = sparse_embedder.__file__
        with open(source) as f:
            content = f.read()

        # Should mention cache configuration
        assert "KNOWGRAPH_PERF_CACHE_SIZE" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
