"""CPG metadata storage and retrieval for query-time code analysis.

Stores CPG paths in graph metadata to enable Joern queries during search.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def save_cpg_metadata(graph_path: Path, cpg_path: Path, entities_count: int = 0) -> None:
    """Save CPG metadata to graph storage.

    Args:
        graph_path: Path to graph storage
        cpg_path: Path to generated CPG
        entities_count: Number of entities extracted
    """
    metadata_dir = graph_path / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    metadata_file = metadata_dir / "cpg_metadata.json"

    metadata = {
        "cpg_path": str(cpg_path),
        "generated_at": datetime.now().isoformat(),
        "entities_count": entities_count,
        "version": "1.0"
    }

    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Saved CPG metadata to {metadata_file}")


def load_cpg_metadata(graph_path: Path) -> Optional[dict]:
    """Load CPG metadata from graph storage.

    Args:
        graph_path: Path to graph storage

    Returns:
        CPG metadata dict or None if not found
    """
    metadata_file = graph_path / "metadata" / "cpg_metadata.json"

    if not metadata_file.exists():
        return None

    try:
        with open(metadata_file) as f:
            metadata = json.load(f)

        # Validate CPG still exists
        cpg_path = Path(metadata["cpg_path"])
        if not cpg_path.exists():
            logger.warning(f"CPG not found at {cpg_path}")
            return None

        return metadata

    except Exception as e:
        logger.error(f"Error loading CPG metadata: {e}")
        return None


def get_cpg_path(graph_path: Path) -> Optional[Path]:
    """Get CPG path for a graph if available.

    Args:
        graph_path: Path to graph storage

    Returns:
        Path to CPG or None
    """
    metadata = load_cpg_metadata(graph_path)

    if not metadata:
        return None

    cpg_path = Path(metadata["cpg_path"])

    if cpg_path.exists():
        return cpg_path
    else:
        return None
