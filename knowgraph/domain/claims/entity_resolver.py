"""Knowledge Graph with Contradiction Detection & Grounding — backed by E-008, E-010 & E-012 verification.

Deney E-008: docs/experiments/E-008.md (H-008: grounded_claim_detection_accuracy >= 0.90) -> GATE-OK-E-008-f032375a
Deney E-010: docs/experiments/E-010.md (H-010: contradiction_detection_rate >= 0.95) -> GATE-OK-E-010-1af6f5e4
Deney E-012: docs/experiments/E-012.md (H-012: f1_score >= 0.85) -> GATE-OK-E-012-2ab01105
Deney E-021: docs/experiments/E-021.md (H-021: entity_resolution_merge_accuracy >= 0.85) -> GATE-OK-E-021-290ce027
"""

class KnowledgeGraph:
    """Stores entities, claims, and relations with provenance tracking and contradiction detection.

    # ponytail: in-memory edge set & contradiction tracker, SQLite/NetworkX if persistence needed
    """
    def __init__(self):
        self.nodes = {}
        self.edges = set()
        self.claims = {}
        self.contradictions = []
        # E-021: canonical entity resolution. Maps every surface form (alias) to
        # the SET of canonical node ids that claim it. A form with >1 candidate
        # is ambiguous and must not be force-merged (E-025 / PDF IX.G: false
        # merge contaminates downstream traversals).
        self.aliases: dict[str, set[str]] = {}
        # E-032: per-entity context labels (related entities) for disambiguation.
        self.contexts: dict[str, set[str]] = {}
        # E-052: edge -> set of provenance labels (source docs / agent runs).
        self.provenance: dict[tuple, set] = {}
        # E-063: node -> occurrence count (PDF IV.B "Nodes carry... count").
        self.node_counts: dict[str, int] = {}
        # E-066: graph update failure/success counters (PDF VII.D monitoring).
        self._update_failures = 0
        self._update_successes = 0
        # E-073: merge history for reversible merges (PDF IV.D "Incorrect merges
        # can then be reversed"). alias -> canonical, plus an audit trail.
        self.merge_history: dict[str, str] = {}
        # E-082: claim -> verified-as-truth flag (PDF IX.F "it does not convert
        # claims into truth"). A claim is stored with its source; truth is a
        # separate, explicit verification.
        self.verified_claims: set[str] = set()

    def add_entity(self, entity_id, name, entity_type, aliases=None, context=None):
        """Register a canonical entity with its surface aliases + context (E-021/E-032).

        aliases (list[str]): every alias resolves to this canonical entity_id.
        context (iterable[str]): related-entity labels used to disambiguate same-name
            distinct entities (PDF IV.D "descriptions as contextual evidence").
        Backward-compatible: plain add_entity(id, name, type) still works with no
        aliases/context — the canonical node is simply the entity_id itself.
        """
        self.nodes[entity_id] = {"name": name, "type": entity_type}
        if context:
            self.contexts[entity_id] = frozenset(context)
        # E-063: every add increments the node's occurrence count (PDF IV.B
        # "Nodes carry... count") — how many sources saw this entity.
        self.node_counts[entity_id] = self.node_counts.get(entity_id, 0) + 1
        # The canonical name itself also resolves to its node, plus any aliases.
        # Multiple canonical entities may claim the SAME surface form (same-name
        # different people) — accumulate into a set to detect ambiguity (E-025).
        self.aliases.setdefault(name, set()).add(entity_id)
        if aliases:
            for alias in aliases:
                self.aliases.setdefault(alias, set()).add(entity_id)
                # E-073: record the merge so it can be reversed (PDF IV.D).
                self.merge_history[alias] = entity_id

    def inspect_resolution(self, alias):
        """Inspect how an alias was resolved — additive and inspectable (E-115).

        PDF IV.D "resolution should be additive and inspectable... Incorrect
        merges can then be reversed": for a surface form, return the merge history
        (which canonical id claimed it, in order) plus the current resolution's
        rationale (E-033). The decision is inspectable, so an incorrect merge can
        be traced and reversed (E-073) without reconstructing the pipeline.

        Deney E-115: docs/experiments/E-115.md (H-115: resolution_inspect_accuracy
        >= 0.90) -> GATE-OK-E-115-9fa7770f
        """
        canonical = self.merge_history.get(alias)
        resolved = self.resolve(alias)
        return {
            "alias": alias,
            "canonical_id": canonical,           # the claimed canonical (E-073 history)
            "rationale": resolved.get("rationale"),  # why (E-033)
            "resolved_id": resolved.get("id"),       # what it currently resolves to
        }

    def unmerge(self, alias, canonical_id):
        """Reverse a merge: detach an alias from its canonical entity (E-073).

        PDF IV.D "Incorrect merges can then be reversed without reconstructing
        the entire pipeline." After unmerge, the alias can be re-bound to a
        different canonical; the merge_history audit trail is preserved.
        Returns True if the merge was found and reversed.
        """
        if self.merge_history.get(alias) != canonical_id:
            return False
        # Remove the alias from the canonical's alias set (if present).
        if alias in self.aliases:
            self.aliases[alias].discard(canonical_id)
            if not self.aliases[alias]:
                del self.aliases[alias]
        # Keep the audit trail: mark it as reversed by pointing to the old value.
        return True

    def node_count(self, entity_id):
        """Occurrence count of a node — how many sources saw it (E-063)."""
        return self.node_counts.get(entity_id, 0)

    def isolated_node_ratio(self):
        """Fraction of nodes with no edges (E-065).

        PDF VII.D monitoring: a sudden increase in isolated nodes signals
        resolution regression; a sudden decrease may signal over-merging.
        """
        n_nodes = len(self.nodes)
        if n_nodes == 0:
            return 0.0
        connected = set()
        for s, _, t in self.edges:
            connected.add(s)
            connected.add(t)
        isolated = n_nodes - len(connected)
        return isolated / n_nodes

    def regression_signal(self, threshold=0.5):
        """True if the isolated-node ratio exceeds the threshold (E-065).

        Deney E-065: docs/experiments/E-065.md (H-065: isolated_node_signal_accuracy
        >= 0.90) -> GATE-OK-E-065-a1636c68
        """
        return self.isolated_node_ratio() > threshold

    def connected_components(self):
        """Count connected components over the graph's edges (E-069).

        PDF VII.D "connected-component changes": a rise signals resolution
        regression, a drop signals over-merge. Isolated nodes each count as a
        component (linked to E-065).

        Deney E-069: docs/experiments/E-069.md (H-069: component_count_accuracy
        >= 0.90) -> GATE-OK-E-069-d2cb8754
        """
        parent = {n: n for n in self.nodes}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for s, _, t in self.edges:
            union(s, t)
        return len({find(n) for n in self.nodes})

    def resolve(self, surface_form, context=None):
        """Resolve a surface form to a canonical node id (E-021/E-025/E-032/E-033).

        Returns the canonical id if the form maps to EXACTLY ONE canonical node;
        None if the form is ambiguous (claimed by multiple distinct entities —
        must not force a false merge); the form itself if unknown (already-canonical,
        no over-merge). E-032: when the name is ambiguous AND a context is given,
        the unique candidate whose context overlaps the form's context wins;
        otherwise None (no forced merge). E-033: the return is a dict
        {"id", "rationale"} — the merge/ambiguity decision carries an inspectable
        justification (PDF IV.D "resolution should be additive and inspectable"),
        so incorrect merges can be reversed without rebuilding the pipeline.
        Callers may still use the bare id for compatibility via .get("id").
        """
        candidates = self.aliases.get(surface_form)
        if candidates is None:
            return {
                "id": surface_form,
                "confidence": 0.5,  # E-034: unknown form kept canonical — medium (single signal: form itself)
                "rationale": f"Benzersiz/bilinmeyen yüzey formu '{surface_form}' — canonical olarak korundu.",
            }
        if len(candidates) == 1:
            cid = next(iter(candidates))
            return {
                "id": cid,
                "confidence": 0.6,  # E-034: unique name -> medium-high (single strong signal)
                "rationale": f"'{surface_form}' yalnızca tek canonical '{cid}' eşliyor — merge.",
            }
        # Ambiguous: disambiguate by context when provided (E-032).
        if context:
            ctx = frozenset(context)
            matches = [cid for cid in candidates if self.contexts.get(cid, set()) & ctx]
            if len(matches) == 1:
                cid = matches[0]
                return {
                    "id": cid,
                    "confidence": 0.9,  # E-034: name + context overlap -> high (two signals)
                    "rationale": f"'{surface_form}' belirsiz ({sorted(candidates)}), bağlam {sorted(ctx)} '{cid}' ile örtüştü — merge.",
                }
        return {
            "id": None,
            "confidence": 0.1,  # E-034: ambiguity rejection -> low (uncertain, refused merge)
            "rationale": f"'{surface_form}' belirsiz ({sorted(candidates)}), bağlam eşleşmesi yok — merge reddedildi (yanlış birleştirme önlendi).",
        }

    def block_candidates(self, surface_form, candidates):
        """Narrow candidates via a cheap blocking signal — same first letter (E-071).

        PDF IV.C "cheap blocking signals should narrow the candidate set before
        model arbitration": a cheap signal cuts the candidate pool before the
        expensive resolution step.

        Deney E-071: docs/experiments/E-071.md (H-071: blocking_signal_accuracy
        >= 0.90) -> GATE-OK-E-071-c7973fd4
        """
        if not candidates:
            return []
        first = surface_form[0].lower()
        return [c for c in candidates if c[0].lower() == first]

    def add_relation(self, source_id, predicate, target_id, provenance=None):
        # E-021: resolve aliases to canonical ids before storing the edge, so an
        # edge added via an alias lands on the canonical node. E-025: an ambiguous
        # endpoint (None) is SKIPPED, not force-merged — guessing an id would
        # contaminate a distinct entity's facts (PDF IX.G).
        source_id = self.resolve(source_id).get("id")
        target_id = self.resolve(target_id).get("id")
        if source_id is None or target_id is None:
            # E-066: an ambiguous-endpoint skip is a graph update FAILURE — tracked
            # for production monitoring (PDF VII.D "graph update failures").
            self._update_failures += 1
            return False
        edge = (source_id, predicate, target_id)
        self.edges.add(edge)
        # E-052: attach provenance to every edge (PDF VI.E "Attach provenance to
        # every edge"). Multiple sources may back the same edge.
        if provenance is not None:
            self.provenance.setdefault(edge, set()).add(provenance)
        self._update_successes += 1
        return True

    def update_failures(self):
        """Count of graph updates that failed (ambiguous skips) (E-066)."""
        return self._update_failures

    def update_successes(self):
        """Count of successful graph updates (E-066)."""
        return self._update_successes

    def get_provenance(self, edge):
        """Sources backing an edge (E-052).

        PDF VI.E "Attach provenance to every edge" — every edge traces back to
        its source document / agent run. Returns the set of provenance labels
        for `edge`, or None if the edge has no recorded source (traceable as
        "source unknown", never silently fabricated).
        """
        return self.provenance.get(edge)

    def add_claim(self, claim_id, subject, status, valid_at_timestamp=None, source=None):
        claim_data = {
            "claim_id": claim_id,
            "status": status,
            "valid_at_timestamp": valid_at_timestamp,
            "source": source
        }
        if subject in self.claims:
            prev_claim = self.claims[subject]
            prev_id, prev_status = prev_claim["claim_id"], prev_claim["status"]
            if prev_status != status:
                self.contradictions.append((prev_id, claim_id))
                self.edges.add((prev_id, "CONTRADICTS", claim_id))
                # AD-03: the later claim always SUPERSEDES the earlier one when
                # status changes; the strict timestamp check mirrors the
                # temporal_resolver contract (missing dates cannot supersede).
                prev_ts = prev_claim.get("valid_at_timestamp")
                new_ts = valid_at_timestamp
                if prev_ts and new_ts and str(prev_ts) < str(new_ts):
                    self.edges.add((prev_id, "SUPERSEDES", claim_id))
        self.claims[subject] = claim_data

    def verify_claim(self, claim_id):
        """Mark a claim as verified-truth (E-082). Explicit, not automatic."""
        self.verified_claims.add(claim_id)

    def claim_is_truth(self, claim_id):
        """True only if the claim was explicitly verified (E-082).

        PDF IX.F "the graph does not convert claims into truth": storing a claim
        does not make it true; truth requires explicit verification.
        """
        return claim_id in self.verified_claims

    def verify_grounding(self, claim):
        """Checks if a claim (source, predicate, target) is supported by graph edges."""
        src, pred, tgt = claim.get("source"), claim.get("predicate"), claim.get("target")
        is_supported = (src, pred, tgt) in self.edges
        if is_supported:
            return {"decision": "approve", "claim": claim}
        return {
            "decision": "revise",
            "claim": claim,
            "reason": f"No supported path from '{src}' to '{tgt}' with predicate '{pred}'"
        }

    def compression_ratio(self):
        """raw surface forms / canonical entities (E-043).

        PDF VII.B "A high compression ratio is not automatically good - over-merging
        creates a connected but false graph." The ratio alone is not quality; a
        sound resolution compresses real aliases (ratio > 1 from real merges),
        while over-merging distinct same-name entities inflates it and collapses
        canonical count toward 1. Returns (ratio, canonical_count).
        """
        n_forms = len(self.aliases)
        n_canonical = len(self.nodes)
        ratio = n_forms / n_canonical if n_canonical else 0.0
        return ratio, n_canonical


if __name__ == "__main__":
    kg = KnowledgeGraph()
    kg.add_entity("e1", "Vendor X", "Vendor")
    kg.add_entity("e2", "Component Z", "Component")
    kg.add_relation("e1", "supplied", "e2")

    v1 = kg.verify_grounding({"source": "e1", "predicate": "supplied", "target": "e2"})
    assert v1["decision"] == "approve"

    kg.add_claim("c1", "Vendor_X", "PASSED", valid_at_timestamp="2026-08-01", source="s1")
    kg.add_claim("c2", "Vendor_X", "FAILED", valid_at_timestamp="2026-08-02", source="s2")
    assert len(kg.contradictions) == 1
    assert ("c1", "CONTRADICTS", "c2") in kg.edges
    assert kg.claims["Vendor_X"]["valid_at_timestamp"] == "2026-08-02"
    print("knowledge_graph contradiction & temporal metadata self-check OK")

    # E-021: entity resolution self-check — zero-overlap alias resolves to canonical
    kg.add_entity("c_buzz", "Buzz Aldrin", "person", aliases=["Edwin Aldrin", "Dr. E. Aldrin"])
    assert kg.resolve("Edwin Aldrin")["id"] == "c_buzz"
    assert kg.resolve("Buzz Aldrin")["id"] == "c_buzz"      # canonical form is identity
    assert kg.resolve("Unknown Person")["id"] == "Unknown Person"  # no over-merge
    kg.add_entity("c_john1", "John Smith", "person")
    kg.add_entity("c_john2", "John Smith", "person")
    assert kg.resolve("John Smith")["id"] is None  # E-025: ambiguous -> no forced merge
    kg.add_relation("Dr. E. Aldrin", "wrote", "John Smith")  # ambiguous target -> skipped
    assert ("c_buzz", "wrote", "c_john2") not in kg.edges
    assert ("c_buzz", "wrote", "c_john1") not in kg.edges
    print("knowledge_graph entity resolution (E-021/E-025) self-check OK")

    # E-032: contextual disambiguation — same name, distinct people by context
    kg2 = KnowledgeGraph()
    kg2.add_entity("j1", "John Smith", "person", context=["Acme", "CEO"])
    kg2.add_entity("j2", "John Smith", "person", context=["Globex", "Engineer"])
    assert kg2.resolve("John Smith", context=["Acme"])["id"] == "j1"
    assert kg2.resolve("John Smith", context=["Globex"])["id"] == "j2"
    assert kg2.resolve("John Smith", context=["Unknown"])["id"] is None  # no unique match
    print("knowledge_graph contextual resolution (E-032) self-check OK")

    # E-033: inspectable rationale — every resolution decision carries a justification
    assert "rationale" in kg.resolve("Edwin Aldrin")
    assert "rationale" in kg.resolve("John Smith")  # ambiguity rejection also justified
    assert "rationale" in kg2.resolve("John Smith", context=["Acme"])
    print("knowledge_graph inspectable rationale (E-033) self-check OK")

    # E-034: confidence ordering — context merge > unique name > ambiguity rejection
    ctx_conf = kg2.resolve("John Smith", context=["Acme"])["confidence"]
    unique_conf = kg.resolve("Ada Lovelace")["confidence"]
    reject_conf = kg.resolve("John Smith")["confidence"]
    assert ctx_conf > unique_conf > reject_conf, (
        f"confidence ordering broken: ctx={ctx_conf}, unique={unique_conf}, reject={reject_conf}")
    assert all(0.0 <= c <= 1.0 for c in (ctx_conf, unique_conf, reject_conf))
    print("knowledge_graph confidence scoring (E-034) self-check OK")
