"""Unit tests for the transferred Graph Engineering entity resolution.

Covers E-021 (alias->canonical), E-025 (ambiguity rejection — never force-merge),
E-032 (context disambiguation), E-033 (inspectable rationale), E-034 (confidence
ordering), and E-073 (reversible merges).
"""

from knowgraph.domain.claims.entity_resolver import KnowledgeGraph


class TestEntityResolutionBasics:
    def test_alias_resolves_to_canonical(self):
        kg = KnowledgeGraph()
        kg.add_entity("c_buzz", "Buzz Aldrin", "person", aliases=["Edwin Aldrin", "Dr. E. Aldrin"])
        assert kg.resolve("Edwin Aldrin")["id"] == "c_buzz"
        assert kg.resolve("Buzz Aldrin")["id"] == "c_buzz"

    def test_unknown_form_kept_canonical(self):
        kg = KnowledgeGraph()
        kg.add_entity("e1", "Vendor X", "Vendor")
        assert kg.resolve("Unknown Person")["id"] == "Unknown Person"

    def test_resolve_returns_rationale(self):
        kg = KnowledgeGraph()
        kg.add_entity("e1", "Vendor X", "Vendor")
        assert "rationale" in kg.resolve("Vendor X")


class TestAmbiguityRejection:
    def test_ambiguous_same_name_no_force_merge(self):
        kg = KnowledgeGraph()
        kg.add_entity("c_john1", "John Smith", "person")
        kg.add_entity("c_john2", "John Smith", "person")
        # E-025: ambiguous -> must NOT force a merge; id is None.
        assert kg.resolve("John Smith")["id"] is None

    def test_ambiguous_relation_skipped(self):
        kg = KnowledgeGraph()
        kg.add_entity("c_buzz", "Buzz Aldrin", "person", aliases=["Edwin Aldrin"])
        kg.add_entity("c_john1", "John Smith", "person")
        kg.add_entity("c_john2", "John Smith", "person")
        kg.add_relation("Edwin Aldrin", "wrote", "John Smith")  # ambiguous target
        # Neither John got the edge (no false merge).
        assert ("c_buzz", "wrote", "c_john1") not in kg.edges
        assert ("c_buzz", "wrote", "c_john2") not in kg.edges
        # The ambiguous-endpoint skip counts as a graph update failure.
        assert kg.update_failures() == 1


class TestContextDisambiguation:
    def test_context_resolves_same_name_distinct_people(self):
        kg = KnowledgeGraph()
        kg.add_entity("j1", "John Smith", "person", context=["Acme", "CEO"])
        kg.add_entity("j2", "John Smith", "person", context=["Globex", "Engineer"])
        assert kg.resolve("John Smith", context=["Acme"])["id"] == "j1"
        assert kg.resolve("John Smith", context=["Globex"])["id"] == "j2"

    def test_context_mismatch_returns_none(self):
        kg = KnowledgeGraph()
        kg.add_entity("j1", "John Smith", "person", context=["Acme"])
        kg.add_entity("j2", "John Smith", "person", context=["Globex"])
        assert kg.resolve("John Smith", context=["Unknown"])["id"] is None


class TestConfidenceAndInspectability:
    def test_confidence_ordering(self):
        kg = KnowledgeGraph()
        kg.add_entity("j1", "John Smith", "person", context=["Acme", "CEO"])
        kg.add_entity("j2", "John Smith", "person", context=["Globex", "Engineer"])
        ctx_conf = kg.resolve("John Smith", context=["Acme"])["confidence"]
        unique_conf = kg.resolve("Ada Lovelace")["confidence"]
        reject_conf = kg.resolve("John Smith")["confidence"]
        assert ctx_conf > unique_conf > reject_conf
        assert all(0.0 <= c <= 1.0 for c in (ctx_conf, unique_conf, reject_conf))

    def test_ambiguity_rejection_has_rationale(self):
        kg = KnowledgeGraph()
        kg.add_entity("c_john1", "John Smith", "person")
        kg.add_entity("c_john2", "John Smith", "person")
        assert "rationale" in kg.resolve("John Smith")


class TestReversibleMerge:
    def test_unmerge_detaches_alias(self):
        kg = KnowledgeGraph()
        kg.add_entity("c1", "Vendor X", "Vendor", aliases=["Acme Corp"])
        assert kg.resolve("Acme Corp")["id"] == "c1"
        assert kg.unmerge("Acme Corp", "c1") is True
        # After unmerge, "Acme Corp" no longer resolves to c1.
        assert kg.resolve("Acme Corp")["id"] == "Acme Corp"

    def test_unmerge_wrong_canonical_returns_false(self):
        kg = KnowledgeGraph()
        kg.add_entity("c1", "Vendor X", "Vendor", aliases=["Acme Corp"])
        assert kg.unmerge("Acme Corp", "c_other") is False


class TestGraphMetrics:
    def test_isolated_node_ratio(self):
        kg = KnowledgeGraph()
        kg.add_entity("e1", "A", "x")
        kg.add_entity("e2", "B", "x")
        kg.add_relation("e1", "ref", "e2")
        assert kg.isolated_node_ratio() == 0.0

    def test_connected_components(self):
        kg = KnowledgeGraph()
        kg.add_entity("e1", "A", "x")
        kg.add_entity("e2", "B", "x")
        kg.add_relation("e1", "ref", "e2")
        assert kg.connected_components() == 1
