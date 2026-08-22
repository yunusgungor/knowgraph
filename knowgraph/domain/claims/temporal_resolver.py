"""Temporal Knowledge Graph Resolver Module for GE-DRE Engine.

Resolves contradictions and temporal updates across entity claims,
generating SUPERSEDES and CONTRADICTS edges.
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta

def _date_sort_key(claim: Dict[str, Any]):
    """Chronological sort key: parse ISO-8601, falling back to a min sentinel.

    # ponytail: string sort was locale-order wrong for denormalized dates; datetime
    # parsing gives real chronology. Non-ISO dates fall back to epoch-min so they
    # can never be misread as "newer" than a dated claim.
    """
    raw = claim.get("valid_at_timestamp") or claim.get("timestamp")
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(str(raw)).isoformat()
    except ValueError:
        return ""  # unparseable -> sentinel, sorts first (never "supersedes")


def tag_temporal_claim(claim: Dict[str, Any], published_at: Optional[str] = None) -> Dict[str, Any]:
    """Resolves relative temporal indicators into absolute ISO-8601 timestamps."""
    tagged = dict(claim)
    if published_at:
        tagged["published_at"] = published_at

    # If valid_at_timestamp exists, maintain it; fallback to timestamp
    valid_ts = tagged.get("valid_at_timestamp") or tagged.get("timestamp")

    if not valid_ts and published_at:
        # Check relative temporal text (ponytail: simple regex stdlib date math)
        temp_text = str(tagged.get("temporal_text", "")).lower().strip()
        pub_dt = datetime.fromisoformat(published_at)

        if temp_text in ("yesterday", "dün"):
            valid_ts = (pub_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            # Bilinmeyen/missing temporal text: `published_at` tarihini bedenin varsayılanı yap
            valid_ts = pub_dt.strftime("%Y-%m-%d")

    tagged["valid_at_timestamp"] = valid_ts or ""
    return tagged


class TemporalResolver:
    """Resolves temporal contradictions and supersedes relationships in Knowledge Graph."""

    def __init__(self, f1_threshold: float = 0.85):
        self.f1_threshold = f1_threshold

    def resolve_claims(self, claims: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Processes a list of claim dicts and resolves temporal contradictions.

        A later-dated claim always SUPERSEDES an earlier one for the same
        (entity, attribute); a CONTRADICTS edge is added only when values differ.
        Edges require a strictly-earlier timestamp (missing/equal dates emit none).

        Claim dict structure:
          {
            "id": str,
            "entity": str,
            "attribute": str,
            "value": str,
            "valid_at_timestamp": str (YYYY-MM-DD),
            "timestamp": str (legacy fallback),
            "source": str
          }
        """
        tagged_claims = [tag_temporal_claim(c) for c in claims]
        groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for c in tagged_claims:
            key = (c["entity"].lower(), c["attribute"].lower())
            groups.setdefault(key, []).append(c)

        supersedes_edges = []
        contradicts_edges = []
        resolved_claims = []

        for (entity, attr), claim_list in groups.items():
            if len(claim_list) < 2:
                resolved_claims.extend(claim_list)
                continue

            # Sort claims by chronological timestamp ascending. Equal dates keep
            # stable list order, and the strict `<` check below prevents spurious
            # SUPERSEDES between contemporaneous claims.
            sorted_claims = sorted(claim_list, key=_date_sort_key)

            # The latest timestamp is active; earlier claims are superseded (regardless
            # of value). Only claims with a real, strictly-earlier date supersede.
            latest_claim = sorted_claims[-1]
            resolved_claims.append(latest_claim)

            for i in range(len(sorted_claims) - 1):
                earlier = sorted_claims[i]
                later = sorted_claims[i+1]

                earlier_ts = _date_sort_key(earlier)
                later_ts = _date_sort_key(later)

                # No temporal basis for an edge when dates are missing or equal: a
                # claim can only supersede another if it is genuinely newer.
                if not earlier_ts or not later_ts or earlier_ts >= later_ts:
                    continue

                supersedes_edges.append({
                    "source": later["id"],
                    "target": earlier["id"],
                    "relation": "SUPERSEDES",
                    "reason": f"Timestamp {later_ts} supersedes {earlier_ts}"
                })
                # A CONTRADICTS edge exists only when the value actually differs.
                if earlier.get("value") != later.get("value"):
                    contradicts_edges.append({
                        "source": later["id"],
                        "target": earlier["id"],
                        "relation": "CONTRADICTS",
                        "reason": f"Value mismatch: '{later.get('value')}' vs '{earlier.get('value')}'"
                    })

        return {
            "status": "success",
            "resolved_claims": resolved_claims,
            "supersedes_edges": supersedes_edges,
            "contradicts_edges": contradicts_edges,
            "total_resolved": len(resolved_claims),
            "total_contradictions": len(contradicts_edges),
            "total_supersedes": len(supersedes_edges)
        }

    def active_claim_at(self, claims, entity, attribute, query_date):
        """Claim active at a given date — point-in-time query (E-044).

        PDF VII.C "respect time and source constraints": a valid answer must find
        the claim active at the query date. Returns the latest claim whose
        valid_at_timestamp <= query_date for the (entity, attribute); None if no
        claim predates the query. Time-ignoring (latest-always) is the falsifiable
        broken behavior this guards against.

        Deney E-044: docs/experiments/E-044.md (H-044: point_in_time_accuracy
        >= 0.90) -> GATE-OK-E-044-34461d5e
        """
        key = (entity.lower(), attribute.lower())
        best = None
        best_ts = ""
        for c in claims:
            tagged = tag_temporal_claim(c)
            if (tagged["entity"].lower(), tagged["attribute"].lower()) != key:
                continue
            ts = tagged.get("valid_at_timestamp") or ""
            if ts and ts <= query_date and ts >= best_ts:
                best, best_ts = tagged, ts
        return best
