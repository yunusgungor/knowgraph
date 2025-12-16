from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder


def test_embed_text():
    embedder = SparseEmbedder()
    text = "hello world hello"
    vector = embedder.embed_text(text)
    # default simple logic: word count?
    # Checking implementation via behavior if I can't see code?
    # I saw code via coverage? No, I saw retriever import it.
    # It likely returns dict {token: count}
    assert vector.get("hello") == 2
    assert vector.get("world") == 1


def test_embed_code():
    embedder = SparseEmbedder()
    code = "def func(): pass"
    vector = embedder.embed_code(code)
    assert "def" in vector
    assert "func" in vector
