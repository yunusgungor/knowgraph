from knowgraph.infrastructure.storage.manifest import (
    Manifest,
    read_manifest,
    update_manifest_stats,
    write_manifest,
)


def test_manifest_creation():
    m = Manifest.create_new("edges.jsonl", "index")
    assert m.version == "1.0.0"
    assert m.node_count == 0
    assert m.edges_filename == "edges.jsonl"


def test_manifest_serialization():
    m = Manifest(
        version="1.0",
        node_count=10,
        edge_count=5,
        file_hashes={"file": "1"},
        edges_filename="e",
        sparse_index_filename="i",
        created_at=100,
        updated_at=200,
    )
    d = m.to_dict()
    assert d["version"] == "1.0"
    assert d["node_count"] == 10

    m2 = Manifest.from_dict(d)
    assert m2.version == m.version
    assert m2.file_hashes == m.file_hashes


def test_write_read_manifest(tmp_path):
    m = Manifest.create_new("edges", "index")
    write_manifest(m, tmp_path)

    assert (tmp_path / "metadata" / "manifest.json").exists()

    m2 = read_manifest(tmp_path)
    assert m2.version == m.version


def test_update_stats():
    m = Manifest.create_new("e", "i")
    m2 = update_manifest_stats(m, 100, 50)
    assert m2.node_count == 100
    assert m2.edge_count == 50
    assert m2.version == m.version
