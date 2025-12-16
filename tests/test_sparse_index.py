from knowgraph.infrastructure.search.sparse_index import SparseIndex


def test_sparse_index_workflow(tmp_path):
    index = SparseIndex()
    # Add docs
    # {term: freq}
    index.add("id1", {"apple": 2, "banana": 1})
    index.add("id2", {"banana": 3, "cherry": 1})

    # Check stats
    assert index.n_docs == 2
    assert index.doc_lengths["id1"] == 3

    # Build
    index.build()
    # avg len: (3 + 4) / 2 = 3.5
    assert index.avg_doc_length == 3.5

    # Search
    # Query: banana
    results = index.search({"banana": 1}, top_k=2)
    # Both have banana. id2 has 3, id1 has 1. id2 should be higher.
    assert len(results) == 2
    assert results[0][0] == "id2"

    # Save
    index.save(tmp_path)
    assert (tmp_path / "sparse_index.json").exists()

    # Load
    index2 = SparseIndex()
    index2.load(tmp_path)
    assert index2.n_docs == 2
    assert index2.avg_doc_length == 3.5
    assert "banana" in index2.index
