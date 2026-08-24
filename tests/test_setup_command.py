"""Tests for the combined ``knowgraph-setup`` command (joern + model).

The install functions are mocked; we only verify orchestration, flag routing,
and exit codes.
"""

from unittest.mock import patch

import pytest

from knowgraph.core.setup import cli_main, cli_main_joern_only


@pytest.fixture
def _patch_installs():
    with (
        patch("knowgraph.core.setup.install_joern") as mock_joern,
        patch("knowgraph.core.setup.install_model") as mock_model,
    ):
        mock_joern.return_value = True
        mock_model.return_value = True
        yield mock_joern, mock_model


class TestCliMain:
    def test_default_runs_both(self, _patch_installs):
        mock_joern, mock_model = _patch_installs
        with pytest.raises(SystemExit) as exc:
            cli_main([])
        assert exc.value.code == 0
        mock_joern.assert_called_once()
        mock_model.assert_called_once()

    def test_joern_only_skips_model(self, _patch_installs):
        mock_joern, mock_model = _patch_installs
        with pytest.raises(SystemExit) as exc:
            cli_main(["--joern-only"])
        assert exc.value.code == 0
        mock_joern.assert_called_once()
        mock_model.assert_not_called()

    def test_model_only_skips_joern(self, _patch_installs):
        mock_joern, mock_model = _patch_installs
        with pytest.raises(SystemExit) as exc:
            cli_main(["--model-only"])
        assert exc.value.code == 0
        mock_joern.assert_not_called()
        mock_model.assert_called_once()

    def test_failure_of_required_component_exits_nonzero(self, _patch_installs):
        mock_joern, mock_model = _patch_installs
        mock_model.return_value = False
        with pytest.raises(SystemExit) as exc:
            cli_main([])  # both required; model failed -> nonzero
        assert exc.value.code == 1
        mock_joern.assert_called_once()
        mock_model.assert_called_once()

    def test_skipped_component_failure_is_ok(self, _patch_installs):
        mock_joern, mock_model = _patch_installs
        mock_model.return_value = False
        with pytest.raises(SystemExit) as exc:
            cli_main(["--joern-only"])  # model not required
        assert exc.value.code == 0


class TestCliMainJoernOnly:
    def test_alias_runs_joern_only(self, _patch_installs):
        mock_joern, mock_model = _patch_installs
        with pytest.raises(SystemExit) as exc:
            cli_main_joern_only()
        assert exc.value.code == 0
        mock_joern.assert_called_once()
        mock_model.assert_not_called()