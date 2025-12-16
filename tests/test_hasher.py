from knowgraph.infrastructure.parsing.hasher import hash_content


def test_hash_content():
    content = "test"
    result = hash_content(content)
    assert isinstance(result, str)
    assert len(result) == 40  # sha1 hex digest length

    # Deterministic
    assert hash_content("test") == result
    assert hash_content("other") != result
