"""Unit tests for the transferred Graph Engineering unitizer (D-1).

Covers the deterministic decomposition + rule-edge regression locks that
Graph Engineering measured (E-204/E-206/E-212/E-219/E-225, GATE-OK): the
unitizer must reproduce the oracle units and never emit a subject-less
fragment.
"""

from knowgraph.domain.claims.unitizer import (
    _coord_split,
    _np_list_split,
    split_sentences,
    unitize,
)


class TestUnitizerBasics:
    def test_oracle_units_from_dense_corpus(self):
        sentences = [
            "Nova Dynamics is a robotics company founded in 2018.",
            "The company is headquartered in Austin, Texas.",
            "Dr. Lena Ortiz has been the CEO of Nova Dynamics since 2021.",
            "Its flagship product is the Atlas robotic arm, released in 2022.",
            "A related firm, Quantum Materials, supplies batteries to Nova Dynamics.",
            "Quantum Materials was founded in 2015 and is led by CEO Rajesh Patel.",
        ]
        oracle = [
            "Nova Dynamics is a robotics company.",
            "Nova Dynamics was founded in 2018.",
            "Nova Dynamics is headquartered in Austin, Texas.",
            "Dr. Lena Ortiz is the CEO of Nova Dynamics.",
            "Dr. Lena Ortiz has been the CEO since 2021.",
            "Nova Dynamics produces the Atlas robotic arm.",
            "The Atlas robotic arm was released in 2022.",
            "Quantum Materials supplies batteries to Nova Dynamics.",
            "Quantum Materials was founded in 2015.",
            "Rajesh Patel leads Quantum Materials.",
        ]
        units, _edges = unitize(sentences)
        assert units == oracle

    def test_rule_edges_produces_and_is_a(self):
        _units, edges = unitize(["Nova Dynamics produces the Atlas robotic arm."])
        assert ("Nova Dynamics", "produces", "the Atlas robotic arm") in edges

    def test_rule_edges_founded_in(self):
        _units, edges = unitize(["Nova Dynamics was founded in 2018."])
        assert ("Nova Dynamics", "founded_in", "2018") in edges

    def test_passthrough_never_emits_broken_fragment(self):
        # A sentence matching no rule must pass through whole, never as a
        # subject-less fragment (E-201 control-b lesson: fragments score 0.00).
        units, edges = unitize(["The system processes requests in real time."])
        assert len(units) == 1
        assert units[0] == "The system processes requests in real time."
        assert edges == []


class TestUnitizerCoordSplit:
    def test_e212_coordinate_split(self):
        sentences = [
            "Quantum Materials coordinates delivery logistics with Nova Dynamics and licenses battery patents to Meridian Labs.",
            "Meridian Labs provides laboratory services to Quantum Materials while managing warranty claims for Atlas.",
        ]
        expected = [
            "Quantum Materials coordinates delivery logistics with Nova Dynamics.",
            "Quantum Materials licenses battery patents to Meridian Labs.",
            "Meridian Labs provides laboratory services to Quantum Materials.",
            "Meridian Labs manages warranty claims for Atlas.",
        ]
        units, _edges = unitize(sentences)
        assert units == expected

    def test_e212_emits_zero_rule_edges(self):
        # E-212 control (a): coordinate split produces units ONLY, never rule
        # edges — the metric cannot be inflated (E-015).
        sentences = [
            "Atlas generates maintenance reports for Meridian Labs and streams telemetry to Quantum Materials.",
        ]
        _units, edges = unitize(sentences)
        assert edges == []


class TestUnitizerNpList:
    def test_e219_np_list_split(self):
        sentences = [
            "Helios Systems negotiates supply agreements with Vertex Robotics and Northwind Labs.",
            "Albion Energy negotiates supply agreements with Helios Systems, Vertex Robotics, and Northwind Labs.",
        ]
        expected = [
            "Helios Systems negotiates supply agreements with Vertex Robotics.",
            "Helios Systems negotiates supply agreements with Northwind Labs.",
            "Albion Energy negotiates supply agreements with Helios Systems.",
            "Albion Energy negotiates supply agreements with Vertex Robotics.",
            "Albion Energy negotiates supply agreements with Northwind Labs.",
        ]
        units, _edges = unitize(sentences)
        assert units == expected

    def test_e219_emits_zero_rule_edges(self):
        _units, edges = unitize(
            ["Helios Systems negotiates supply agreements with Vertex Robotics and Northwind Labs."]
        )
        assert edges == []


class TestUnitizerDirectNpList:
    def test_e225_direct_object_np_list(self):
        sentences = [
            "Helios Systems supplies batteries and control units to Quantum Materials.",
            "Quantum Materials licenses its solid-state cells and sodium packs to Helios Systems.",
        ]
        expected = [
            "Helios Systems supplies batteries to Quantum Materials.",
            "Helios Systems supplies control units to Quantum Materials.",
            "Quantum Materials licenses its solid-state cells to Helios Systems.",
            "Quantum Materials licenses sodium packs to Helios Systems.",
        ]
        units, _edges = unitize(sentences)
        assert units == expected


class TestSentenceSplitter:
    def test_abbreviation_protection(self):
        # "Dr. Lena Ortiz" must stay one sentence (its period is protected).
        sentences = split_sentences(
            "Dr. Lena Ortiz has been the CEO of Nova Dynamics since 2021. Nova Dynamics is based in Austin."
        )
        assert len(sentences) == 2
        assert sentences[0].startswith("Dr. Lena Ortiz")

    def test_newline_is_sentence_boundary(self):
        sentences = split_sentences("First line.\nSecond line.")
        assert len(sentences) == 2

    def test_empty_returns_empty(self):
        assert split_sentences("") == []

    def test_newline_after_period_no_double_period(self):
        # Markdown bodies frequently end a line with a period before the next
        # heading; split_sentences must not turn that into a double period.
        sentences = split_sentences("KnowGraph indexes source code.\n## Features\nThe tool is fast.")
        assert all(".." not in s for s in sentences)
        assert sentences[0] == "KnowGraph indexes source code. ## Features."
        assert sentences[-1] == "The tool is fast."

    def test_newline_without_period_becomes_sentence_end(self):
        sentences = split_sentences("First line\nSecond line.")
        assert sentences == ["First line.", "Second line."]


class TestUnitizerNoSubjectFragment:
    def test_np_list_split_returns_none_for_non_list(self):
        # _np_list_split must return None (passthrough) for a sentence with no
        # preposition-headed NP-list, never a broken fragment.
        result = _np_list_split("Nova Dynamics produces the Atlas robotic arm.")
        assert result is None

    def test_coord_split_returns_none_without_and(self):
        result = _coord_split("Nova Dynamics produces the Atlas robotic arm.")
        assert result is None
