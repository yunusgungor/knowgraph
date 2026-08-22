"""Unit tests for the transferred Graph Engineering TemporalResolver.

Covers SUPERSEDES/CONTRADICTS edge generation (E-010, E-117) and point-in-time
querying (E-044): "stale fact never current".
"""

from knowgraph.domain.claims.temporal_filter import active_claims_at
from knowgraph.domain.claims.temporal_resolver import TemporalResolver, tag_temporal_claim


class TestTemporalResolverClaims:
    def test_later_claim_supersedes_earlier(self):
        resolver = TemporalResolver()
        claims = [
            {"id": "c1", "entity": "Acme", "attribute": "CEO", "value": "Alice",
             "valid_at_timestamp": "2023-01-01"},
            {"id": "c2", "entity": "Acme", "attribute": "CEO", "value": "Bob",
             "valid_at_timestamp": "2024-01-01"},
        ]
        result = resolver.resolve_claims(claims)
        assert len(result["supersedes_edges"]) == 1
        assert result["supersedes_edges"][0]["source"] == "c2"
        assert result["supersedes_edges"][0]["target"] == "c1"
        # Values differ -> CONTRADICTS too.
        assert len(result["contradicts_edges"]) == 1

    def test_same_value_no_contradicts(self):
        resolver = TemporalResolver()
        claims = [
            {"id": "c1", "entity": "Acme", "attribute": "CEO", "value": "Bob",
             "valid_at_timestamp": "2023-01-01"},
            {"id": "c2", "entity": "Acme", "attribute": "CEO", "value": "Bob",
             "valid_at_timestamp": "2024-01-01"},
        ]
        result = resolver.resolve_claims(claims)
        assert len(result["supersedes_edges"]) == 1  # newer supersedes older regardless
        assert len(result["contradicts_edges"]) == 0  # same value -> no contradiction

    def test_missing_date_no_supersedes(self):
        resolver = TemporalResolver()
        claims = [
            {"id": "c1", "entity": "Acme", "attribute": "CEO", "value": "Alice"},
            {"id": "c2", "entity": "Acme", "attribute": "CEO", "value": "Bob"},
        ]
        result = resolver.resolve_claims(claims)
        assert len(result["supersedes_edges"]) == 0
        assert len(result["contradicts_edges"]) == 0

    def test_equal_dates_no_supersedes(self):
        resolver = TemporalResolver()
        claims = [
            {"id": "c1", "entity": "Acme", "attribute": "CEO", "value": "Alice",
             "valid_at_timestamp": "2024-01-01"},
            {"id": "c2", "entity": "Acme", "attribute": "CEO", "value": "Bob",
             "valid_at_timestamp": "2024-01-01"},
        ]
        result = resolver.resolve_claims(claims)
        assert len(result["supersedes_edges"]) == 0

    def test_resolved_claims_keeps_latest(self):
        resolver = TemporalResolver()
        claims = [
            {"id": "c1", "entity": "Acme", "attribute": "CEO", "value": "Alice",
             "valid_at_timestamp": "2023-01-01"},
            {"id": "c2", "entity": "Acme", "attribute": "CEO", "value": "Bob",
             "valid_at_timestamp": "2024-01-01"},
        ]
        result = resolver.resolve_claims(claims)
        resolved_ids = [c["id"] for c in result["resolved_claims"]]
        assert resolved_ids == ["c2"]  # only the latest survives


class TestTemporalResolverPointInTime:
    def test_active_claim_at_query_date(self):
        resolver = TemporalResolver()
        claims = [
            {"id": "c1", "entity": "Acme", "attribute": "CEO", "value": "Alice",
             "valid_at_timestamp": "2023-01-01"},
            {"id": "c2", "entity": "Acme", "attribute": "CEO", "value": "Bob",
             "valid_at_timestamp": "2024-01-01"},
        ]
        # Before Bob's claim -> Alice is active.
        assert resolver.active_claim_at(claims, "Acme", "CEO", "2023-12-31")["value"] == "Alice"
        # After Bob's claim -> Bob is active.
        assert resolver.active_claim_at(claims, "Acme", "CEO", "2024-06-30")["value"] == "Bob"

    def test_active_claims_at_helper(self):
        claims = [
            {"id": "c1", "entity": "Acme", "attribute": "CEO", "value": "Alice",
             "valid_at_timestamp": "2023-01-01"},
            {"id": "c2", "entity": "Acme", "attribute": "CEO", "value": "Bob",
             "valid_at_timestamp": "2024-01-01"},
        ]
        active = active_claims_at(claims, "2023-12-31")
        assert len(active) == 1
        assert active[0]["value"] == "Alice"


class TestTemporalResolverTag:
    def test_tag_relative_temporal_defaults_to_published(self):
        resolver = TemporalResolver()
        claims = [
            {"id": "c1", "entity": "Acme", "attribute": "CEO", "value": "Alice",
             "temporal_text": "recent"},
        ]
        result = resolver.resolve_claims(claims)
        # No published_at -> no timestamp -> no supersedes, claim kept raw.
        assert len(result["supersedes_edges"]) == 0
        assert len(result["resolved_claims"]) == 1

    def test_tag_yesterday(self):
        # "yesterday" relative to a published_at resolves to the day before it.
        tagged = tag_temporal_claim(
            {"id": "c1", "entity": "Acme", "attribute": "CEO", "value": "Alice",
             "temporal_text": "yesterday"},
            published_at="2026-08-22",
        )
        assert tagged["valid_at_timestamp"] == "2026-08-21"
