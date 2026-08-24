"""Embedding-model installation and management."""

from knowgraph.core.models.manager import (
    MODEL_DIR,
    MODEL_ID,
    MODEL_LOCAL_PATH,
    cli_main,
    install_model,
    verify_model_installed,
)

__all__ = [
    "MODEL_DIR",
    "MODEL_ID",
    "MODEL_LOCAL_PATH",
    "cli_main",
    "install_model",
    "verify_model_installed",
]
