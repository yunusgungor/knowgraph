"""Grounding Evaluator & Zero-Hallucination Ratchet Loop Module for GE-DRE Engine.

Verifies generated report claims against Knowledge Graph edges and filters
out unbacked/hallucinated statements to enforce 0-hallucination policy.
"""

import copy
import re
from typing import List, Dict, Any, Tuple, Set


def _norm(value: str) -> str:
    """Normalize a triple component: collapse internal whitespace, strip, lowercase.

    Callers guarantee str (non-str components are filtered before this runs).
    """
    return re.sub(r"\s+", " ", value).strip().lower()


def _is_str_triple(t) -> bool:
    """True if t is a 3-tuple/list of str components (usable as evidence)."""
    return isinstance(t, (tuple, list)) and len(t) == 3 and all(
        isinstance(x, str) for x in t
    )


_LABELS = ("subject", "predicate", "object")


def _revise_claim(claim_components: Tuple[str, str, str],
                  supported_set: Set[Tuple[str, str, str]]) -> Tuple[bool, Tuple[str, str, str] | None, int]:
    """Deterministic, evidence-anchored, non-fabricating claim revision (E-020).

    Given a normalized (s, p, o) claim NOT in supported_set, try to align it to a
    supporting triple by filling exactly ONE divergent position. Anti-fabrication
    rules (AD-04 / E-015 lesson):

      1. WHO is not rewritten. The subject is the entity identity of the claim;
         it must never be re-authored. Only a divergent *predicate* (1) or
         *object* (2) slot is a candidate for alignment; a divergent subject
         makes the claim irrevisable.
      2. Single-anchor, single-meaning only. The divergent position must resolve
         to a UNIQUE anchor triple. If two different anchors would fill the same
         divergent position with different values (a tie), revision is refused
         rather than fabricating a guess.

    Returns (True, anchor, divergent_pos) when revision is safe, else (False, None, -1).
    Pure and deterministic: no LLM, no network. sorted() iteration + set is
    reproducible; ties are rejected regardless of iteration order.
    """
    s, p, o = claim_components
    candidates = []  # (divergent_pos, anchor triple)
    for anchor in sorted(supported_set):
        as_, ap, ao = anchor
        div = (as_ != s, ap != p, ao != o)
        if sum(div) != 1:
            continue  # not exactly one divergence
        div_pos = div.index(True)
        if div_pos == 0:
            continue  # subject divergence -> cannot re-author WHO
        candidates.append((div_pos, anchor))

    if not candidates:
        return False, None, -1
    first_pos, first_anchor = candidates[0]
    for pos, anchor in candidates[1:]:
        # A tie = same divergent position filling different values. Refuse.
        if pos == first_pos and anchor[first_pos] != first_anchor[first_pos]:
            return False, None, -1
    # first_anchor's fill value is the unique, KG-anchored value for that slot.
    return True, first_anchor, first_pos


def derive_aligned_claim(claim: Dict[str, str], anchor: Tuple[str, str, str],
                         div_pos: int) -> Dict[str, str]:
    """Fill exactly the divergent position (predicate/object) from the anchor.

    Anti-fabrication: the subject (identity) is preserved verbatim — WHO is never
    rewritten. Only the single divergent non-subject slot is set to the anchor's
    value, making the revised claim groundable without asserting a new entity.
    Return a new dict; input not mutated.
    """
    aligned = copy.deepcopy(claim)
    key = _LABELS[div_pos]
    aligned[key] = anchor[div_pos]
    return aligned


def build_supported_map(kg_triples) -> Dict[Tuple[str, str, str], Tuple[str, str, str]]:
    """Normalize KG triples -> their first-seen ORIGINAL-cased form.

    The revision pass aligns a claim to an anchor triple; preserving the KG's
    original casing (rather than the normalized lowercase form) keeps the
    revised claim human-readable and identical to real evidence. Deterministic:
    first-seen original is kept per normalized triple.
    """
    mapping: Dict[Tuple[str, str, str], Tuple[str, str, str]] = {}
    for t in kg_triples:
        if not _is_str_triple(t):
            continue
        triple = (_norm(t[0]), _norm(t[1]), _norm(t[2]))
        if not any(triple):
            continue
        mapping.setdefault(triple, (t[0], t[1], t[2]))
    return mapping


def build_supported_set(kg_triples) -> Set[Tuple[str, str, str]]:
    """Normalize and collect KG triples into a ground-truth supported set.

    Malformed/non-str triples and all-empty triples are skipped (AD-04 gate
    bypass guard, E-016 lesson). Shared between evaluate_and_filter and the
    revision mode so both agree on the anchor universe.
    """
    supported_set: Set[Tuple[str, str, str]] = set()
    for t in kg_triples:
        if not _is_str_triple(t):
            continue  # skip malformed / non-str triples
        triple = (_norm(t[0]), _norm(t[1]), _norm(t[2]))
        if not any(triple):
            continue  # an all-empty triple is not evidence (AD-04 gate bypass)
        supported_set.add(triple)
    return supported_set


class GroundingEvaluator:
    """Evaluates and filters report claims against Knowledge Graph evidence."""

    def __init__(self, precision_threshold: float = 0.95):
        self.precision_threshold = precision_threshold

    def evaluate_and_filter(
        self,
        claims: List[Dict[str, str]],
        kg_triples: List[Tuple[str, str, str]]
    ) -> Dict[str, Any]:
        """Evaluates claims against KG triples (Subject, Predicate, Object).

        Returns approved claims, rejected claims, and grounding precision metric.
        """
        supported_set = build_supported_set(kg_triples)

        approved_claims: List[Dict[str, str]] = []
        rejected_claims: List[Dict[str, str]] = []

        for claim in claims:
            s, p, o = claim.get("subject"), claim.get("predicate"), claim.get("object")
            if not all(isinstance(x, str) for x in (s, p, o)):
                # Missing/None/non-str component -> cannot be grounded; reject.
                triple = ("", "", "")  # never present in supported_set (empty excluded)
            else:
                triple = (_norm(s), _norm(p), _norm(o))

            if triple in supported_set:
                c_copy = copy.deepcopy(claim)
                c_copy["grounded"] = True
                c_copy["status"] = "APPROVED"
                approved_claims.append(c_copy)
            else:
                c_copy = copy.deepcopy(claim)
                c_copy["grounded"] = False
                c_copy["status"] = "REJECTED_UNBACKED"
                c_copy["rejection_reason"] = "No supporting edge in Knowledge Graph"
                rejected_claims.append(c_copy)

        total = len(claims)
        grounding_precision = (len(approved_claims) / total) if total > 0 else 1.0

        return {
            "status": "success",
            "approved_claims": approved_claims,
            "rejected_claims": rejected_claims,
            "grounding_precision": grounding_precision,
            "total_evaluated": total,
            "total_approved": len(approved_claims),
            "total_rejected": len(rejected_claims)
        }


class QueryPathEvaluator:
    """Validates multi-hop answer paths edge-by-edge against the KG (E-024).

    PDF VII.C "Query Evaluation": a valid multi-hop answer must cite edges that
    actually exist in the graph — "fluent answers can cite irrelevant edges"
    (Tablo III). Validates each cited (src, rel, tgt) edge for membership in the
    KG; fabricated or reversed edges fail. Pure, deterministic, stdlib-only.

    AI-7 (E-031): also scores adjacency integrity — consecutive cited edges
    that form a chain (edge[i].target == edge[i+1].source). Fragmented synthesis
    keeps every edge valid (edge-by-edge = 1.0) but loses adjacency (PDF IX.E);
    adjacency_integrity captures that loss independently of edge validity.
    """

    def __init__(self):
        pass

    def evaluate(self, answers, graph_edges):
        """Validate each cited edge against the graph + adjacency integrity.

        Args:
            answers: list of dicts {"id": str, "cited_edges": [(src, rel, tgt), ...]}
            graph_edges: iterable of (src, rel, tgt) triples present in the KG.

        Returns:
            {"valid_edges", "total_edges", "cited_path_validity",
             "adjacency_integrity", "per_answer": [...]}
        """
        edge_set = set(graph_edges)
        valid = 0
        total = 0
        # Adjacency opportunities: within each answer, consecutive edges may chain.
        # Fragmented synthesis (each edge its own answer) has ZERO opportunities
        # because no answer carries two consecutive edges — so it scores 0.0.
        total_adjacent_pairs = 0
        total_adjacent_ok = 0
        per_answer = []
        for ans in answers:
            cited = ans.get("cited_edges", [])
            valid_in = sum(1 for e in cited if e in edge_set)
            valid += valid_in
            total += len(cited)
            # Adjacency: consecutive cited edges form a chain when target[i] == source[i+1].
            # Opportunities = len(cited) - 1 (only in answers with >=2 edges).
            adj_pairs = max(0, len(cited) - 1)
            adj_ok = sum(
                1 for i in range(adj_pairs)
                if cited[i][2] == cited[i + 1][0]  # target[i] == source[i+1]
            )
            total_adjacent_pairs += adj_pairs
            total_adjacent_ok += adj_ok
            per_answer.append({
                "id": ans["id"],
                "valid": valid_in,
                "total": len(cited),
                "adjacent_pairs": adj_pairs,
                "adjacent_ok": adj_ok,
            })
        score = (valid / total) if total else 1.0
        # AI-7: adjacency integrity = realized chains / opportunities. Fragmented
        # synthesis (every edge isolated) has 0 opportunities -> 0.0; coherent has
        # all opportunities realized -> 1.0. When no answer carries >=2 edges, the
        # integrity is genuinely 0 (no chain exists), not a vacuous 1.0.
        adj_score = (total_adjacent_ok / total_adjacent_pairs) if total_adjacent_pairs else 0.0
        return {
            "valid_edges": valid,
            "total_edges": total,
            "cited_path_validity": score,
            "adjacency_integrity": adj_score,
            "per_answer": per_answer,
        }

    def detect_gaps(self, answers, graph_edges):
        """Mark missing-evidence gaps in each answer's cited path (E-045).

        PDF VII.C "identify missing evidence": a gap exists at a consecutive
        pair when the cited edge is absent from the graph (missing edge, checked
        on EVERY cited edge including the last) or when target[i] != source[i+1]
        (broken chain / non-adjacent jump). Returns {answer_id: [gap_desc, ...]}.

        Deney E-045: docs/experiments/E-045.md (H-045: missing_evidence_detection
        >= 0.90) -> GATE-OK-E-045-249750a7
        """
        edge_set = set(graph_edges)
        gaps = {}
        for ans in answers:
            cited = ans.get("cited_edges", [])
            ans_gaps = []
            for e in cited:
                if e not in edge_set:
                    ans_gaps.append(f"edge {e} not in graph")
            for i in range(len(cited) - 1):
                if cited[i][2] != cited[i + 1][0]:
                    ans_gaps.append(f"non-adjacent: {cited[i][2]} != {cited[i + 1][0]}")
            gaps[ans["id"]] = ans_gaps
        return gaps

    def classify_claim(self, claim, graph_edges, max_hops=2):
        """Classify a cited claim as fact | inference | unsupported (E-046).

        PDF VII.C "distinguish fact from inference": a claim whose edge is
        DIRECTLY in the graph is a FACT; one derivable via a 2-hop path but not
        directly present is an INFERENCE; neither is UNSUPPORTED. The system must
        not present inference as fact.

        Deney E-046: docs/experiments/E-046.md (H-046: fact_inference_accuracy
        >= 0.90) -> GATE-OK-E-046-718bb98c
        """
        src, pred, tgt = claim
        edge_set = set(graph_edges)
        if (src, pred, tgt) in edge_set:
            return "fact"
        adjacency = {}
        for s, p, t in graph_edges:
            adjacency.setdefault(s, []).append((p, t))
        for _, t in adjacency.get(src, []):
            for p2, t2 in adjacency.get(t, []):
                if t2 == tgt:
                    return "inference"
        return "unsupported"


class RatchetLoop:
    """Karpathy Ratchet Loop — strips unbacked claims from a draft report.

    Wraps GroundingEvaluator.evaluate_and_filter and produces the report-shaped
    output: only grounded (approved) claims survive, and the grounding precision
    is logged alongside the strip counts. Deterministic plumbing of the verified
    classifier — no new evidence logic here.
    """

    def __init__(self, evaluator=None, precision_threshold: float = 0.95,
                 revision_fn=None):
        self.evaluator = evaluator if evaluator is not None else GroundingEvaluator(
            precision_threshold=precision_threshold)
        # ponytail: precision_threshold documents the FR-002.2 (>=0.95) intent but
        # is intentionally inert — raw grounding_precision is not a valid gate
        # (E-013/E-015 lesson: approved/total is misleading). Real gating lives in
        # tests/benchmarks as grounding_accuracy against ground truth.
        self.precision_threshold = precision_threshold
        # revision_fn is injected via constructor (2.2 review discipline: booby
        # logic must not be monkeypatched / no global-state mutation) so tests
        # can falsify the E-020 metric with a broken transform.
        self.revision_fn = revision_fn if revision_fn is not None else _revise_claim

    def run(self, draft_report: List[Dict[str, str]], kg_triples: List[Tuple[str, str, str]],
            revision_mode: bool = False) -> Dict[str, Any]:
        """Runs the ratchet pass on a draft report.

        Args:
            draft_report: report claims; unbacked ones are stripped or (when
                revision_mode=True) revised to an evidence-anchored form.
            kg_triples: KG evidence triples used as the grounding anchor universe.
            revision_mode: when True, recoverable unbacked claims are revised to
                status="REVISED", grounded=True (E-020); irredeemable ones are
                still stripped. Output report then holds only APPROVED + REVISED,
                every retained claim groundable. Filter-only contract (False) is
                preserved unchanged (AC #5).

        Returns:
            filtered_report: retained (APPROVED and, in revision_mode, REVISED)
                claims.
            evaluation: the raw GroundingEvaluator result (approve/reject split).
            log: {"grounding_precision", "total_evaluated", "total_stripped",
                  "total_revised", "total_stripped_unrevised", "revision_reports"}
        """
        # Guard non-list / None inputs (2.2 review discipline).
        draft_report = list(draft_report) if draft_report is not None else []
        draft_report = [c for c in draft_report if isinstance(c, dict)]
        kg_triples = list(kg_triples) if kg_triples is not None else []
        evaluation = self.evaluator.evaluate_and_filter(draft_report, kg_triples)

        log = {
            "grounding_precision": evaluation["grounding_precision"],
            "total_evaluated": evaluation["total_evaluated"],
            "total_stripped": evaluation["total_rejected"],
        }
        filtered_report = evaluation["approved_claims"]

        if revision_mode:
            supported_map = build_supported_map(kg_triples)
            supported_set = set(supported_map)
            revised = []
            stripped = []
            for claim in evaluation["rejected_claims"]:
                s, p, o = claim.get("subject"), claim.get("predicate"), claim.get("object")
                if not all(isinstance(x, str) for x in (s, p, o)):
                    # Non-str / missing component -> no anchor possible: strip.
                    stripped_claim = copy.deepcopy(claim)
                    stripped_claim["rejection_reason"] = (
                        "Revision impossible: non-str/missing claim component")
                    stripped.append(stripped_claim)
                    continue
                norm = (_norm(s), _norm(p), _norm(o))
                revisable, norm_anchor, div_pos = self.revision_fn(norm, supported_set)
                if revisable:
                    anchor = supported_map.get(norm_anchor)
                    if anchor is None:
                        # Injected booby revision_fn fabricated an anchor not in the
                        # KG -> cannot ground; refuse (anti-fabrication).
                        stripped_claim = copy.deepcopy(claim)
                        stripped_claim["rejection_reason"] = (
                            "No revision possible: revision anchor not in Knowledge Graph")
                        stripped.append(stripped_claim)
                        continue
                    # anti-fabrication: keep WHO verbatim, fill only the divergent
                    # predicate/object slot from the anchor, and clear the stale
                    # rejection_reason left by evaluate_and_filter.
                    revised_claim = copy.deepcopy(claim)
                    revised_claim["grounded"] = True
                    revised_claim["status"] = "REVISED"
                    revised_claim.pop("rejection_reason", None)
                    revised_claim["revised_from"] = copy.deepcopy(claim)
                    revised_claim["anchor_triple"] = anchor
                    derived = derive_aligned_claim(revised_claim, anchor, div_pos)
                    revised_claim.update(derived)
                    revised.append(revised_claim)
                else:
                    stripped_claim = copy.deepcopy(claim)
                    stripped_claim["rejection_reason"] = (
                        "No revision possible: no unique supporting edge for the divergent component")
                    stripped.append(stripped_claim)

            filtered_report = evaluation["approved_claims"] + revised
            # AC #3: report precision over the ACTUAL retained (output) report.
            total_retained = len(filtered_report)
            grounded_retained = sum(1 for c in filtered_report if c.get("grounded"))
            log["grounding_precision"] = (
                grounded_retained / total_retained if total_retained else 1.0)
            log.update({
                "total_revised": len(revised),
                "total_stripped_unrevised": len(stripped),
                "total_revision_anchors": len(supported_set),
            })

        return {
            "filtered_report": filtered_report,
            "evaluation": evaluation,
            "log": log,
        }
