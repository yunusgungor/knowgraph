"""Embedding-model installation and management for KnowGraph.

Downloads the `sentence-transformers/all-MiniLM-L6-v2` model into
``~/.knowgraph/models/`` at setup time so runtime retrieval never stalls on an
unexpected ~80MB Hub download. Mirrors the Joern manager pattern
(``knowgraph/core/joern/manager.py``): idempotent, UTF-8-safe output, bool
return mapped to an exit code by ``cli_main``.
"""

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"

# Single source of truth for the .knowgraph home (mirrors joern manager).
KNOWGRAPH_HOME = Path.home() / ".knowgraph"
MODEL_DIR = KNOWGRAPH_HOME / "models"
MODEL_LOCAL_PATH = MODEL_DIR / "all-MiniLM-L6-v2"

# The model's fingerprint file; its presence marks a complete download.
_MODEL_CONFIG = "config.json"

# Imported lazily but held at module level so the setup path and tests can both
# reference/patch it cleanly. huggingface_hub ships as a transitive dep of
# sentence-transformers, but guard it anyway (a plain offline install of a
# stripped environment may lack it).
try:
    from huggingface_hub import snapshot_download as snapshot_download
except Exception:  # pragma: no cover - depends on optional deps
    snapshot_download = None  # type: ignore


def verify_model_installed() -> bool:
    """Return True when the local model folder is present and usable."""
    return (MODEL_LOCAL_PATH / _MODEL_CONFIG).exists()


def install_model() -> bool:
    """Download the embedding model into ``~/.knowgraph/models`` if absent.

    Returns True on success (or if already installed); False on a download
    failure. A missing model is NON-fatal — dense retrieval falls back to the
    local-hash embedder — so callers treat False as a warning, not a crash.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    print("\n" + "=" * 60)
    print("🧠 KnowGraph - Embedding Model Setup")
    print("=" * 60 + "\n")

    # Step 0: Already installed?
    print("🔍 Checking for existing embedding model...")
    if verify_model_installed():
        print("\n✅ Model is already installed and verified!")
        print(f"   Location: {MODEL_LOCAL_PATH}")
        print("   Dense (semantic) retrieval is available.\n")
        return True

    # Step 1: sentence-transformers must be importable to download + verify.
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        print("\n⚠️  sentence-transformers is not installed.")
        print("   Install it with:  pip install 'knowgraph[hybrid]'")
        print("   Then re-run:      knowgraph-setup")
        print("\n   Dense retrieval will use the built-in local fallback until then.\n")
        return False

    # Step 2: Download the full model folder into ~/.knowgraph/models.
    if snapshot_download is None:
        print("\n⚠️  huggingface_hub is not available.")
        print("   Install it with:  pip install 'knowgraph[hybrid]'")
        print("   Then re-run:      knowgraph-setup\n")
        return False
    try:
        print(f"📥 Downloading {MODEL_ID} (~80MB) ...")
        print(f"   Target: {MODEL_LOCAL_PATH}")
        snapshot_download(repo_id=MODEL_ID, local_dir=str(MODEL_LOCAL_PATH))
    except Exception as e:
        logger.error(f"❌ Model download failed: {e}")
        print(f"\n❌ Failed to download the model: {e}")
        print("   Dense retrieval will use the built-in local fallback until then.\n")
        return False

    # Step 3: Verify.
    if not verify_model_installed():
        print("\n❌ Model download verification failed (config.json missing).")
        print("   Dense retrieval will use the built-in local fallback.\n")
        return False

    print("\n✅ Model installed successfully!")
    print(f"   Location: {MODEL_LOCAL_PATH}")
    print("   Dense (semantic) retrieval is now available.\n")
    return True


def cli_main() -> None:
    """Console-script entry point for ``knowgraph-setup`` model install."""
    logging.basicConfig(level=logging.INFO)
    success = install_model()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    cli_main()
