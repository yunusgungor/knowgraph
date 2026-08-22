"""Temporal query filter — active-at-a-date retrieval over SUPERSEDES/CONTRADICTS.

Wraps the Graph Engineering TemporalResolver (E-044/E-117 measured) with
query-date-aware helpers for the knowgraph query path. The core guarantee,
carried over verbatim from Graph Engineering: "stale fact never current" — a
claim superseded at the query date is never presented as if it were fact.

Deterministic, stdlib-only, no LLM.
"""

from knowgraph.domain.claims.temporal_resolver import tag_temporal_claim


def active_claims_at(claims, query_date):
    """Return the claims ACTIVE at ``query_date`` (point-in-time, E-044).

    For each (entity, attribute) group, only the claim with the latest
    ``valid_at_timestamp`` that is ``<= query_date`` is active. Superseded /
    future-dated claims are dropped. Time-ignoring (latest-always) is the
    broken behavior this guards against.

    Args:
    ----
        claims: list of claim dicts (entity, attribute, value, valid_at_timestamp)
        query_date: ISO date string (e.g. "2026-08-22")

    Returns:
    -------
        List of active claim dicts.

    """
    groups: dict[tuple[str, str], list] = {}
    for c in claims:
        key = (str(c.get("entity", "")).lower(), str(c.get("attribute", "")).lower())
        groups.setdefault(key, []).append(c)

    active = []
    for members in groups.values():
        best, best_ts = None, ""
        for c in members:
            tagged = tag_temporal_claim(c)
            ts = tagged.get("valid_at_timestamp") or ""
            if ts and ts <= query_date and ts >= best_ts:
                best, best_ts = tagged, ts
        if best is not None:
            active.append(best)
    return active


def _edge_parts(e):
    """Normalize an edge to a (source, type, target) 3-tuple.

    Accepts both ``(s, r, t)`` triples/lists and knowgraph ``Edge`` models
    (which expose ``source``/``type``/``target`` attributes).
    """
    if hasattr(e, "source") and hasattr(e, "type") and hasattr(e, "target"):
        return e.source, e.type, e.target
    return e[0], e[1], e[2]


def superseded_targets(edges):
    """Return the set of stale node ids — the TARGETS of supersedes edges.

    ``build_temporal_edges`` writes ``(newer_conv, "supersedes", older_conv)``
    edges: the target is the superseded conversation. This helper extracts the
    stale conversation ids so callers can drop their edges/claims.
    """
    return {_edge_parts(e)[2] for e in edges if _edge_parts(e)[1] == "supersedes"}


def filter_edges_by_temporal(edges, query_date):
    """Drop edges sourced from a superseded conversation (stale fact).

    ``edges`` is a list of ``(source, relation, target)`` triples or knowgraph
    ``Edge`` models. A supersedes edge marks its target conversation as stale;
    any edge whose source is a stale conversation is removed. ``query_date`` is
    accepted for symmetry with ``active_claims_at``; the supersedes edges already
    carry the resolved order, so the date is not consulted here. Edges with no
    temporal basis pass through unchanged.
    """
    edge_list = list(edges)
    stale = superseded_targets(edge_list)
    if not stale:
        return edge_list
    return [e for e in edge_list if _edge_parts(e)[0] not in stale]
