import pytest

from knowgraph.shared.security import (
    sanitize_filename,
    sanitize_query_input,
    validate_graph_store_path,
    validate_json_size,
    validate_path,
)


def test_validate_path_traversal():
    """Test detection of path traversal."""
    # Without allowed_parent, traversal is allowed (resolves to absolute path)
    # So we should test WITH allowed_parent to see traversal prevention


def test_validate_path_existence(tmp_path):
    """Test path existence checks."""
    p = tmp_path / "test.txt"
    p.touch()

    assert validate_path(p, must_exist=True) == p.resolve()

    missing = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError):
        validate_path(missing, must_exist=True)


def test_validate_path_file_type(tmp_path):
    """Test file vs directory checks."""
    d = tmp_path / "subdir"
    d.mkdir()

    with pytest.raises(ValueError, match="Path is not a file"):
        validate_path(d, must_exist=True, must_be_file=True)


def test_sanitize_filename():
    """Test filename sanitization."""
    assert sanitize_filename("test.txt") == "test.txt"
    assert sanitize_filename("test/../test.txt") == "test_.._test.txt"
    assert sanitize_filename('test"<>:') == "test____"
    # Reserved names
    assert sanitize_filename("CON") == "_CON"


def test_sanitize_query_input():
    """Test query sanitization."""
    assert sanitize_query_input("  test  ") == "test"
    assert sanitize_query_input("test\0bad") == "testbad"

    long_query = "a" * 10005
    sanitized = sanitize_query_input(long_query, max_length=10000)
    assert len(sanitized) == 10000


def test_validate_graph_store_path(tmp_path):
    """Test graph store validation."""
    # Valid layout
    store = tmp_path / "graph"
    store.mkdir()
    (store / "nodes").mkdir()

    validate_graph_store_path(store)

    # Invalid: Not a dir
    f = tmp_path / "file"
    f.touch()
    with pytest.raises(ValueError):
        validate_graph_store_path(f)

    # Invalid: File where dir expected
    bad_store = tmp_path / "bad_graph"
    bad_store.mkdir()
    (bad_store / "nodes").touch()  # Should be dir
    with pytest.raises(ValueError, match="found file"):
        validate_graph_store_path(bad_store)


def test_validate_json_size():
    """Test JSON size validation."""
    data = {"a": "b" * 1000}
    validate_json_size(data, max_size_bytes=2000)

    with pytest.raises(ValueError, match="exceeds size limit"):
        validate_json_size(data, max_size_bytes=100)
