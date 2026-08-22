"""Unit tests for the transferred Graph Engineering grounding evaluator.

Covers GroundingEvaluator (E-008: grounded claim detection), QueryPathEvaluator
(E-024/E-046: cited-path validity + fact/inference classification), and the
RatchetLoop (zero-hallucination stripping).
"""

from knowgraph.domain.claims.grounding_evaluator import (
    GroundingEvaluator,
    QueryPathEvaluator,
    RatchetLoop,
)


class TestGroundingEvaluator:
    def test_grounded_claim_approved(self):
        kg_triples = [("Nova Dynamics", "produces", "Atlas")]
        evaluator = GroundingEvaluator()
        result = evaluator.evaluate_and_filter(
            [{"subject": "Nova Dynamics", "predicate": "produces", "object": "Atlas"}],
            kg_triples,
        )
        assert len(result["approved_claims"]) == 1
        assert result["approved_claims"][0]["grounded"] is True
        assert result["grounding_precision"] == 1.0

    def test_ungrounded_claim_rejected(self):
        kg_triples = [("Nova Dynamics", "produces", "Atlas")]
        evaluator = GroundingEvaluator()
        result = evaluator.evaluate_and_filter(
            [{"subject": "Nova Dynamics", "predicate": "invents", "object": "Zeppelin"}],
            kg_triples,
        )
        assert len(result["rejected_claims"]) == 1
        assert result["rejected_claims"][0]["grounded"] is False
        assert result["grounding_precision"] == 0.0

    def test_missing_component_rejected_not_crashed(self):
        evaluator = GroundingEvaluator()
        result = evaluator.evaluate_and_filter(
            [{"subject": None, "predicate": "produces", "object": "Atlas"}],
            [("Nova Dynamics", "produces", "Atlas")],
        )
        assert len(result["rejected_claims"]) == 1


class TestQueryPathEvaluator:
    def test_valid_path_passes(self):
        qpe = QueryPathEvaluator()
        graph_edges = [("A", "ref", "B"), ("B", "ref", "C")]
        answers = [{"id": "a1", "cited_edges": [("A", "ref", "B"), ("B", "ref", "C")]}]
        result = qpe.evaluate(answers, graph_edges)
        assert result["cited_path_validity"] == 1.0
        assert result["adjacency_integrity"] == 1.0

    def test_fabricated_edge_fails(self):
        qpe = QueryPathEvaluator()
        graph_edges = [("A", "ref", "B")]
        answers = [{"id": "a1", "cited_edges": [("A", "ref", "Z")]}]
        result = qpe.evaluate(answers, graph_edges)
        assert result["cited_path_validity"] == 0.0

    def test_classify_claim_fact(self):
        qpe = QueryPathEvaluator()
        assert qpe.classify_claim(("A", "ref", "B"), [("A", "ref", "B")]) == "fact"

    def test_classify_claim_inference(self):
        qpe = QueryPathEvaluator()
        graph_edges = [("A", "ref", "B"), ("B", "ref", "C")]
        assert qpe.classify_claim(("A", "ref", "C"), graph_edges) == "inference"

    def test_classify_claim_unsupported(self):
        qpe = QueryPathEvaluator()
        assert qpe.classify_claim(("A", "ref", "Z"), [("A", "ref", "B")]) == "unsupported"


class TestRatchetLoop:
    def test_strips_unbacked_claims(self):
        kg_triples = [("Nova Dynamics", "produces", "Atlas")]
        loop = RatchetLoop()
        draft = [
            {"subject": "Nova Dynamics", "predicate": "produces", "object": "Atlas"},
            {"subject": "Nova Dynamics", "predicate": "invents", "object": "Zeppelin"},
        ]
        result = loop.run(draft, kg_triples)
        assert len(result["filtered_report"]) == 1
        assert result["filtered_report"][0]["object"] == "Atlas"
        assert result["log"]["total_stripped"] == 1

    def test_revision_mode_fills_single_slot(self):
        kg_triples = [("Nova Dynamics", "produces", "Atlas")]
        loop = RatchetLoop(revision_fn=None)  # default deterministic revision
        draft = [
            # object diverges from the anchor -> revisable (only object slot differs)
            {"subject": "Nova Dynamics", "predicate": "produces", "object": "Zeppelin"},
        ]
        result = loop.run(draft, kg_triples, revision_mode=True)
        retained = result["filtered_report"]
        assert len(retained) == 1
        assert retained[0]["status"] == "REVISED"
        assert retained[0]["object"] == "Atlas"
        assert retained[0]["grounded"] is True

    def test_revision_never_rewrites_subject(self):
        kg_triples = [("Nova Dynamics", "produces", "Atlas")]
        loop = RatchetLoop()
        draft = [
            # subject diverges -> irrevisable, stripped
            {"subject": "Quantum Materials", "predicate": "produces", "object": "Atlas"},
        ]
        result = loop.run(draft, kg_triples, revision_mode=True)
        assert result["filtered_report"] == []
        assert result["log"]["total_stripped_unrevised"] == 1
