"""Unit tests for the embedding-model manager (no real download)."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _patch_model_paths(monkeypatch, tmp_path):
    """Point MODEL_LOCAL_PATH at a temp dir so tests never touch ~/.knowgraph."""
    import knowgraph.core.models.manager as m

    monkeypatch.setattr(m, "MODEL_LOCAL_PATH", tmp_path / "models" / "all-MiniLM-L6-v2")
    monkeypatch.setattr(m, "MODEL_DIR", tmp_path / "models")
    yield
    # Ensure verify_model_installed reads the patched path.
    m.MODEL_LOCAL_PATH = tmp_path / "models" / "all-MiniLM-L6-v2"


class TestInstallModel:
    def test_skips_download_when_already_installed(self, tmp_path, monkeypatch):
        """Idempotent: config.json present -> no snapshot_download call."""
        import knowgraph.core.models.manager as m

        (tmp_path / "models" / "all-MiniLM-L6-v2").mkdir(parents=True, exist_ok=True)
        (tmp_path / "models" / "all-MiniLM-L6-v2" / "config.json").write_text("{}")

        with patch("knowgraph.core.models.manager.snapshot_download") as mock_dl:
            assert m.install_model() is True
            mock_dl.assert_not_called()

    def test_downloads_to_local_dir(self, tmp_path, monkeypatch):
        """Calls snapshot_download with the right repo_id + local_dir; updates MODEL_LOCAL_PATH."""
        import knowgraph.core.models.manager as m

        fake_model_dir = tmp_path / "models" / "all-MiniLM-L6-v2"
        monkeypatch.setattr(m, "MODEL_LOCAL_PATH", fake_model_dir)
        monkeypatch.setattr(m, "MODEL_DIR", tmp_path / "models")

        calls = []

        def spy(**kwargs):
            calls.append(kwargs)
            fake_model_dir.mkdir(parents=True, exist_ok=True)
            (fake_model_dir / "config.json").write_text("{}")

        with patch("knowgraph.core.models.manager.snapshot_download", side_effect=spy):
            assert m.install_model() is True
        assert calls and calls[0]["repo_id"] == m.MODEL_ID
        assert calls[0]["local_dir"] == str(fake_model_dir)

    def test_missing_sentence_transformers_returns_false(self, monkeypatch):
        """When sentence-transformers isn't importable, install fails gracefully."""
        import knowgraph.core.models.manager as m

        real_import = __import__

        def fake_import(name, *a, **k):
            if name == "sentence_transformers":
                raise ImportError("no")
            return real_import(name, *a, **k)

        with patch("builtins.__import__", side_effect=fake_import):
            assert m.install_model() is False

    def test_download_failure_returns_false(self, monkeypatch):
        """A download exception returns False (non-fatal)."""
        import knowgraph.core.models.manager as m

        with patch(
            "knowgraph.core.models.manager.snapshot_download",
            side_effect=RuntimeError("network down"),
        ):
            assert m.install_model() is False


class TestVerifyModelInstalled:
    def test_true_when_config_present(self, tmp_path):
        import knowgraph.core.models.manager as m

        d = tmp_path / "models" / "all-MiniLM-L6-v2"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text("{}")
        m.MODEL_LOCAL_PATH = d
        assert m.verify_model_installed() is True

    def test_false_when_absent(self, tmp_path):
        import knowgraph.core.models.manager as m

        m.MODEL_LOCAL_PATH = tmp_path / "nope" / "all-MiniLM-L6-v2"
        assert m.verify_model_installed() is False


class TestCliMain:
    def test_exit_zero_on_success(self, monkeypatch):
        import knowgraph.core.models.manager as m

        monkeypatch.setattr(m, "install_model", lambda: True)
        with pytest.raises(SystemExit) as exc:
            m.cli_main()
        assert exc.value.code == 0

    def test_exit_one_on_failure(self, monkeypatch):
        import knowgraph.core.models.manager as m

        monkeypatch.setattr(m, "install_model", lambda: False)
        with pytest.raises(SystemExit) as exc:
            m.cli_main()
        assert exc.value.code == 1