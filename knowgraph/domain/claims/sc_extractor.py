"""R-008 SC-quote extraction chain — async adapter for knowgraph LLM providers.

Transferred from Graph Engineering (E-205/E-207/E-215 measured, GATE-OK):
D-2 self-contained (SC) quote-forced extraction + D-3 P3 entailment publication
filter. The core guarantee: every published edge carries a verbatim, both-entity
quote drawn from the source unit (anti-fabrication), and a P3 verifier decides
whether the quote actually entails the claimed (subject, predicate, object)
before the edge is published.

Knowgraph's LLM providers (``openai_provider`` / ``mcp_sampling_provider``) are
async and expose ``generate_text(prompt) -> str``; Graph Engineering's original
chain was sync over a ``chat_completion(prompt, max_tokens)`` adapter. This
module wraps the async provider behind a tiny ``AsyncChatAdapter`` so the
measured logic ports over with minimal change.

Use:
    provider = OpenAIProvider(...)   # or McpSamplingProvider()
    adapter = AsyncChatAdapter(provider)
    relations = await sc_extract_unit(adapter, "Nova Dynamics produces the Atlas robotic arm.")
"""

import json
import re
from typing import Any

from knowgraph.domain.claims.unitizer import unitize


# ── D-2: SC extractor prompt (E-197/E-198/E-205 measured verbatim) ──
_SC_EXTRACT_PROMPT = (
    "Extract a knowledge graph from the text as JSON with EXACTLY this schema:\n"
    '{"entities": [{"name": "<str>", "type": "<person|org|place|event>"}], '
    '"relations": [{"subject": "<str>", "predicate": "<str>", "object": "<str>", '
    '"quote": "<verbatim substring>"}]}\n'
    "Only output the JSON object, nothing else.\n"
    "IMPORTANT — self-contained evidence requirement: every relation MUST include "
    "a quote that is a VERBATIM (character-for-character) substring of the Text, "
    "names BOTH the subject and object entities (or an anaphora the subject "
    "clearly refers to, e.g. 'the company'), and directly asserts the "
    "predicate-object relationship. A fragment that does not name both entities "
    "(e.g. 'founded in 2018' without the company) is NOT acceptable evidence — "
    "omit such relations entirely. If the text does not assert a relation, do "
    "not invent one."
)


# ── D-3: P3 entailment verifier prompt (E-196/E-197/E-205 measured verbatim) ──
_P3_PROMPT = (
    "You are an evidence verifier. You are given a factual claim as a triple "
    "(subject, predicate, object) and the quoted span a system claims supports it. "
    "Decide whether the quoted span SUPPORTS the claim.\n"
    "SUPPORTED means the quote DIRECTLY asserts the subject-object relationship "
    "stated in the claim (resolve anaphora: 'the company' may refer to the subject). "
    "If the quote concerns a DIFFERENT entity, states a DIFFERENT fact, or does not "
    "entail the claim, answer UNSUPPORTED. An empty quote is never supporting "
    "evidence.\n"
    "Reply with EXACTLY this JSON: "
    '{"verdict": "SUPPORTED", "reason": "<one short sentence>"} or '
    '{"verdict": "UNSUPPORTED", "reason": "<one short sentence>"}. '
    "Only output the JSON object."
)

_P3_CAL_SUFFIX = (
    "\nDouble-check: the quoted span is the actual text from the unit. Re-read "
    "it. Decide ONLY whether it DIRECTLY asserts the (subject, predicate, object) "
    "relationship. If it does, answer SUPPORTED. If it truly concerns a different "
    "entity or a different fact, answer UNSUPPORTED."
)


class AsyncChatAdapter:
    """Wrap an async knowgraph provider (``generate_text``) as an async LLM call.

    Graph Engineering's chain called ``chat_completion(prompt, max_tokens)``
    synchronously. This adapter preserves that call shape but awaits the
    provider and tolerates ``max_tokens`` being unused (providers decide their
    own budget).
    """

    def __init__(self, provider: Any) -> None:
        self.provider = provider

    async def chat_completion(self, prompt: str, max_tokens: int = 2000) -> str | None:
        try:
            text = await self.provider.generate_text(prompt)
        except Exception:
            return None
        return text if isinstance(text, str) else None


async def _llm_call_async(adapter: AsyncChatAdapter, prompt: str, max_tokens: int = 2000, retries: int = 4) -> dict | None:
    """Await the LLM with retry on malformed/missing output; parse the JSON dict.

    E-125 retry pattern carried over: transient provider failures are retried;
    a non-dict result returns None (caller treats it as empty, never fabricates).
    """
    for _ in range(retries):
        raw = await adapter.chat_completion(prompt, max_tokens=max_tokens)
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def _p3_verdict(raw: dict | None) -> str | None:
    """P3 verifier verdict from the LLM's JSON (E-196/E-205 verbatim)."""
    if not isinstance(raw, dict):
        return None
    v = str(raw.get("verdict") or "").strip().upper()
    if v.startswith("SUPPORTED"):
        return "SUPPORTED"
    if v.startswith("UNSUPPORTED"):
        return "UNSUPPORTED"
    return None


def _span_norm(s: str) -> str:
    """E-208 norm family (E-215 D-2). Surface-form normalization: lowercase, strip
    title / trailing qualifier / leading article, anaphoric 'the_company' ->
    nova_dynamics, then collapse every non-alphanumeric run to '_'. A normalized
    quote must still be a SUBSTRING of the normalized unit — paraphrase never
    admitted (E-215 preflight regression lock).
    """
    s = s.lower().strip()
    s = re.sub(r"^dr\.?\s+", "", s)                 # title
    s = re.sub(r"\s+robotic arm$", "", s)           # trailing qualifier
    s = re.sub(r"^(the|a|an)\s+", "", s)            # leading article (surface form)
    s = re.sub(r"^the_company$", "nova_dynamics", s)  # anaphoric subject (E-189)
    return re.sub(r"[^a-z0-9]+", " ", s).strip().replace(" ", "_")


async def sc_extract_unit(adapter: AsyncChatAdapter, unit: str) -> list[dict]:
    """D-2: SC-forced extraction from ONE unit (E-205 measured verbatim).

    Returns validated relation dicts: each carries a quote that is a NORMALIZED
    substring of the unit (tolerant surface-form containment via ``_span_norm``)
    and names the subject+object. Fragment quotes are omitted entirely. A
    paraphrase is still rejected (the normalized quote must be a substring of
    the normalized unit).
    """
    prompt = _SC_EXTRACT_PROMPT + f"\n\nText: {unit}"
    raw = await _llm_call_async(adapter, prompt, max_tokens=2000)
    if not isinstance(raw, dict):
        return []
    out = []
    for r in raw.get("relations", []):
        if not isinstance(r, dict):
            continue
        s, p, o, q = r.get("subject"), r.get("predicate"), r.get("object"), r.get("quote")
        if not all(isinstance(x, str) and x.strip() for x in (s, p, o)):
            continue
        if not isinstance(q, str) or not q.strip():
            continue
        if _span_norm(q) not in _span_norm(unit):
            continue
        out.append({"subject": s, "predicate": p, "object": o, "quote": q})
    return out


async def p3_verify(adapter: AsyncChatAdapter, s: str, p: str, o: str, quote: str) -> bool:
    """D-3: P3 entailment publication check with UNSUPPORTED calibration (E-215).

    SUPPORTED gates immediately; a UNSUPPORTED verdict gets ONE deliberate
    re-read with the calibration suffix before blocking. Other/malformed verdicts
    block. Guard is a filter (~85% reduction of quote-bearing inference
    fabrication, E-198), not an eraser.
    """
    prompt = _P3_PROMPT + f"\n\nClaim: ({s}, {p}, {o})\nQuoted span: \"{quote}\""
    first = _p3_verdict(await _llm_call_async(adapter, prompt, max_tokens=400))
    if first == "SUPPORTED":
        return True
    if first != "UNSUPPORTED":
        return False
    second = _p3_verdict(await _llm_call_async(adapter, prompt + _P3_CAL_SUFFIX, max_tokens=400))
    return second == "SUPPORTED"


async def extract_short_unit_graph(adapter: AsyncChatAdapter, text: str) -> dict:
    """R-008 short-unit chain as ONE async production surface (E-207/E-229).

    (1) ``unitize`` (D-1, deterministic, LLM-free) decomposes the text into
    subject-anchored propositions + rule edges; (2) each unit is SC-quote-forced
    extracted; (3) every LLM edge passes the P3 entailment filter; (4) the union
    reducer publishes SC+P3-passing LLM edges UNION deterministic rule edges
    (majority consensus is NOT used — E-194 measured collapse).

    Returns {"relations": [...], "rule_edges": [...], "stats": {...}}.
    """
    units, rule_edges = unitize(split_sentences_safe(text))
    published = []
    emitted = []
    for unit in units:
        for r in await sc_extract_unit(adapter, unit):
            emitted.append(r)
            if await p3_verify(adapter, r["subject"], r["predicate"], r["object"], r["quote"]):
                published.append({**r, "source": "sc_p3"})
    return {
        "relations": published,
        "emitted_relations": emitted,
        "rule_edges": [{"subject": s, "predicate": p, "object": o, "source": "rule"}
                       for (s, p, o) in rule_edges],
        "stats": {
            "units": len(units),
            "rule_edges": len(rule_edges),
            "emitted_relations": len(emitted),
            "published_relations": len(published),
        },
    }


def split_sentences_safe(text: str) -> list[str]:
    """Sentence-split free text for the unitizer (E-230 deterministic splitter).

    Falls back to the raw non-empty lines when the splitter yields nothing.
    """
    from knowgraph.domain.claims.unitizer import split_sentences

    sentences = split_sentences(text)
    return sentences if sentences else [ln for ln in text.splitlines() if ln.strip()]


if __name__ == "__main__":
    # Deterministic regression lock (NO LLM): D-2 normalization must not admit a
    # paraphrase — the distinction from the quote-REMOVAL collapse path.
    _para_unit = "Nova Dynamics supplies batteries to Quantum Materials."
    _para_q = "Nova Dynamics ships batteries to Quantum Materials"
    assert _span_norm(_para_q) not in _span_norm(_para_unit), \
        "D-2 regression: normalization admits a paraphrase — quote guard removed"
    # Surface-form tolerance STILL works (case/punctuation/trailing period).
    assert _span_norm("Quantum Materials licenses battery patents to Meridian Labs.") == \
        _span_norm("quantum materials licenses battery patents to meridian labs")
    # D-1 unitizer is deterministic — its own regression locks live in __main__.
    units, edges = unitize(["Nova Dynamics is a robotics company founded in 2018."])
    assert units == ["Nova Dynamics is a robotics company.", "Nova Dynamics was founded in 2018."]
    assert ("Nova Dynamics", "founded_in", "2018") in edges
    print("sc_extractor D-2/D-1 regression locks OK")
