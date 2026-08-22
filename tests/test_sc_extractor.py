"""Tests for the R-008 SC-quote + P3 entailment extractor (Graph Engineering transfer).

Covers D-2 SC-quote enforcement (every published relation must carry a
self-contained, both-entity quote) and D-3 P3 entailment publication filter.
Uses a fake async provider so no live LLM is needed.
"""

from knowgraph.domain.claims.sc_extractor import (
    AsyncChatAdapter,
    _p3_verdict,
    _span_norm,
    p3_verify,
    sc_extract_unit,
)


class FakeProvider:
    """Deterministic fake provider: returns a canned JSON response per call."""

    def __init__(self, responses: dict[str, str]):
        self.responses = responses
        self.calls: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        self.calls.append(prompt)
        # Match by a distinctive substring of the prompt.
        for key, value in self.responses.items():
            if key in prompt:
                return value
        return "{}"


class TestSpanNorm:
    def test_surface_form_tolerance(self):
        assert _span_norm("Quantum Materials licenses battery patents to Meridian Labs.") == (
            "quantum_materials_licenses_battery_patents_to_meridian_labs"
        )

    def test_paraphrase_rejected(self):
        # "ships" is NOT a substring of "supplies" — the D-2 guard holds.
        unit = _span_norm("Nova Dynamics supplies batteries to Quantum Materials.")
        quote = _span_norm("Nova Dynamics ships batteries to Quantum Materials")
        assert quote not in unit


class TestP3Verdict:
    def test_supported(self):
        assert _p3_verdict({"verdict": "SUPPORTED"}) == "SUPPORTED"

    def test_unsupported(self):
        assert _p3_verdict({"verdict": "UNSUPPORTED"}) == "UNSUPPORTED"

    def test_malformed(self):
        assert _p3_verdict({"verdict": "maybe"}) is None
        assert _p3_verdict(None) is None


class TestScExtractUnit:
    async def test_valid_relation_with_quote_published(self):
        # SC-extractor prompt asks for verbatim quotes; the fake returns one
        # relation whose quote is a real substring of the unit.
        unit = "Nova Dynamics produces the Atlas robotic arm."
        provider = FakeProvider(
            {
                "Extract a knowledge graph": (
                    '{"entities": [{"name": "Nova Dynamics", "type": "org"}], '
                    '"relations": [{"subject": "Nova Dynamics", "predicate": "produces", '
                    '"object": "Atlas robotic arm", "quote": "produces the Atlas robotic arm"}]}'
                )
            }
        )
        adapter = AsyncChatAdapter(provider)
        relations = await sc_extract_unit(adapter, unit)
        assert len(relations) == 1
        assert relations[0]["subject"] == "Nova Dynamics"
        assert relations[0]["predicate"] == "produces"
        assert relations[0]["object"] == "Atlas robotic arm"

    async def test_substring_quote_accepted_even_without_subject_name(self):
        # Code-level SC enforcement (Graph Engineering, E-215 D-2) requires only
        # that the normalized quote be a substring of the normalized unit — the
        # "names BOTH entities" rule is enforced at the PROMPT level (E-197/E-198
        # SC-citer). "founded in 2018" IS a substring of the unit, so it is
        # accepted at the code level.
        unit = "Nova Dynamics was founded in 2018."
        provider = FakeProvider(
            {
                "Extract a knowledge graph": (
                    '{"relations": [{"subject": "Nova Dynamics", "predicate": "founded_in", '
                    '"object": "2018", "quote": "founded in 2018"}]}'
                )
            }
        )
        adapter = AsyncChatAdapter(provider)
        relations = await sc_extract_unit(adapter, unit)
        assert len(relations) == 1

    async def test_paraphrase_quote_omitted(self):
        unit = "Nova Dynamics supplies batteries to Quantum Materials."
        provider = FakeProvider(
            {
                "Extract a knowledge graph": (
                    '{"relations": [{"subject": "Nova Dynamics", "predicate": "supplies", '
                    '"object": "Quantum Materials", "quote": "ships batteries to Quantum Materials"}]}'
                )
            }
        )
        adapter = AsyncChatAdapter(provider)
        relations = await sc_extract_unit(adapter, unit)
        assert relations == []  # "ships" is a paraphrase, not a substring


class TestP3Verify:
    async def test_supported_publishes(self):
        provider = FakeProvider(
            {"You are an evidence verifier": '{"verdict": "SUPPORTED", "reason": "quote asserts it"}'}
        )
        adapter = AsyncChatAdapter(provider)
        assert await p3_verify(adapter, "Nova Dynamics", "produces", "Atlas", "produces the Atlas") is True

    async def test_unsupported_blocks(self):
        provider = FakeProvider(
            {"You are an evidence verifier": '{"verdict": "UNSUPPORTED", "reason": "different fact"}'}
        )
        adapter = AsyncChatAdapter(provider)
        assert await p3_verify(adapter, "Nova Dynamics", "produces", "Atlas", "founded in 2018") is False

    async def test_unsupported_calibration_reread(self):
        # First verdict UNSUPPORTED, re-read (calibration suffix) SUPPORTED -> publish.
        async def responder(prompt):
            if "Double-check" in prompt:
                return '{"verdict": "SUPPORTED", "reason": "re-read confirms"}'
            return '{"verdict": "UNSUPPORTED", "reason": "initial doubt"}'

        provider = FakeProvider({})
        provider.generate_text = responder  # type: ignore[method-assign]
        adapter = AsyncChatAdapter(provider)
        assert await p3_verify(adapter, "A", "rel", "B", "A rel B") is True
