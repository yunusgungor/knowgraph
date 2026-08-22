"""D-1 Deterministic Unitizer + rule edges (R-008, E-204/E-206) — stdlib-only, no LLM.

Deney E-204: docs/experiments/E-204.md (H-204: d1_combined_recall >= 0.90)
  -> GATE-OK-E-204-220766f8 (D-1 unitizer oracle parity 0.85; temporal rule
     edges -> combined 0.95, ADVISORY-BLOCK n=40).
Deney E-206: docs/experiments/E-206.md (H-206: d1_combined_accuracy >= 0.90)
  -> GATE-OK-E-206-7f7adca1 (VERIFIED — code lock opened; produces/is-a rule
     edges close E-205's two model-level miss classes -> 1.0000 (40/40)).
Deney E-212: docs/experiments/E-212.md (H-212: coord_split_dense_composite_accuracy >= 0.90)
  -> GATE-OK-E-212-af19241b (VERIFIED — coordinate-clause split + subject
     propagation + narrow gerund->finite closes E-211's multi-clause composite
     frontier: kilo chain 0.39 -> 1.0000 (36/36), 0 rule edges).
Deney E-218: docs/experiments/E-218.md (H-218: d1_generalized_accuracy >= 0.90)
  -> GATE-OK-E-218-08fb2b9d (VERIFIED — long-subject decomposition generalizes:
     R1-R4 on 24 fresh composite sentences, kilo pooled 120/120 = 1.0000,
     precision 1.00, 0 rule edges; E-213/E-214/E-216 "unitizer doesn't split"
     roots close in production).
Deney E-219: docs/experiments/E-219.md (H-219: det_np_list_accuracy >= 0.90)
  -> GATE-OK-E-219-031f3db3 (VERIFIED — object-coordination NP-list split:
     preposition-headed lists -> one single-clause unit per member, kilo
     pooled 112/112 = 1.0000, Wilson 0.9668, 0 rule edges; flash 8/8
     production guarantee preserved; closes R-008 §5 measured-remaining
     surface).

Turns a dense multi-sentence document into (a) subject-anchored, self-contained
propositions (<= 1 sentence each, the E-160 %100 extraction regime) and
(b) rule-based deterministic edges (the E-127/E-174 pattern: dates are parsed
deterministically, never by the LLM). E-206 extends the rule-edge set from
temporal (founded_in / released_in / ceo_since) to verb/class surfaces:
`X produces Y` and `X is a Y` — the two classes E-205 measured as persistent
model-level misses even in a single clause (E-202 lesson).

Rules are PRE-COMMITTED (E-204.md / E-206.md, written BEFORE measurement —
anti-E-015). They are the deterministic encoding of the E-202 measured lesson:
possessive 's ("Nova Dynamics' flagship product"), passive "is led by", and
anaphora ("The company", "Its") break the model's subject selection;
subject-anchored active re-rendering fixes it. Each rule is a general
linguistic pattern; a sentence that matches no rule is passed through (after
anaphora + appositive stripping) rather than dropped or emitted broken
(E-201 control-b lesson: subject-less fragments score 0.00).

Rule edges are published WITHOUT the P3 entailment guard (deterministic code,
not model claims — the guard filters model inference-fabrication, not rule
output; their quotes are fragments P3 would reject).

Documented limitations (prototype scope): anaphora resolution is
pattern-based (last-org memory, not full coreference); temporal-cue subject
attribution uses the sentence-initial phrase heuristic.

Output contract:
  units      : list[str] — subject-anchored propositions (one per gold fact)
  rule_edges : list[(s, p, o)] — deterministic edges (LLM-free)
"""

import re

# E-230: deterministic sentenceizer (text -> sentences), the production INPUT
# of the short-unit chain. LLM-free; unitizer operates on a sentence list, but
# the production surface receives free text. Measured in docs/experiments/E-230.md
# (pre-committed corpus/gold, anti-E-015).
_SENT_END_RE = re.compile(r"(?<=[.!?])\s+")
# Abbreviation titles whose period is NOT a sentence end ("Dr. Lena Ortiz",
# "Prof. X", "Mr. S", "Inc.", "Ltd."). The period is kept and the text after
# the space is only a sentence break if it starts an uppercase (capitalized)
# word OTHER than these titles. Simpler robust rule: never split after a known
# abbreviation token; always split after [.!?] followed by whitespace+capital.
_ABBR = ("dr", "prof", "mr", "mrs", "ms", "st", "inc", "ltd", "co",
         "corp", "eg", "ie", "etc", "vs", "jr", "sr")
# Matches an abbreviation TOKEN (word) optionally followed by a period — the
# period is protected, not a sentence end: "Dr." / "Inc." / "Ltd." etc.
_ABBR_RE = re.compile(r"\b(" + "|".join(_ABBR) + r")\.", re.IGNORECASE)


def split_sentences(text):
    """Deterministic sentence splitter (E-230). Returns non-empty stripped
    sentences. Splits on '.', '!', '?' followed by whitespace+capital (or end),
    EXCEPT after an abbreviation token ("Dr. Lena" stays one sentence: its
    period is protected). Newlines are always sentence boundaries.
    """
    if not text:
        return []
    # Normalize newlines to hard sentence boundaries first.
    text = re.sub(r"\s*\n\s*", "\n", text.strip())
    # A line that already ends in sentence punctuation (`.`, `!`, `?`) becomes a
    # plain break; otherwise the newline is a sentence end (`\n` -> `. `). This
    # avoids "graph.\n## Features" => "graph.. ## Features" (knowgraph markdown
    # bodies frequently end lines with a period before the next heading).
    text = re.sub(r"(?<=[.!?])\n", " ", text)
    text = text.replace("\n", ". ")  # remaining newline => sentence end
    # Protect abbreviation periods (keep the token's period, sentinel the rest).
    protected = {}

    def _protect(m):
        key = f"\x00{len(protected)}\x00"
        protected[key] = m.group(0)  # e.g. "Dr."
        return key

    text = _ABBR_RE.sub(_protect, text)
    # Split on sentence-ending punctuation followed by space + capital (or end).
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'0-9\x00])", text)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        for key, tok in protected.items():
            p = p.replace(key, tok)
        if p.strip(" .!?") != "":
            out.append(p)
    return out
_PRODUCT_NOUNS = ("flagship product", "main product", "product", "latest product")
_TEMP_VERBS = ("founded", "established", "incorporated", "launched", "released",
               "introduced")
_PASSIVE_VERB = {"led": "leads", "headed": "heads", "run": "runs"}
_PERSON_MARK = ("dr.", "prof.", "mr.", "mrs.", "ms.")
_SKIP_INITIAL = {"the", "a", "an", "its", "it", "they"}

# E-212: coordinate-clause split + subject propagation (pre-committed rule,
# docs/experiments/E-212.md; GATE-OK-E-212-af19241b, VERIFIED). Applied only on
# the passthrough branch of _split_clauses; produces UNITS only, NEVER rule
# edges (E-212 control (a) == 0 — the metric cannot be inflated, E-015).
_COORD_RE = re.compile(r"\s+(?:and|while)\s+")
_DET_PREP = {"the", "a", "an", "its", "it", "this", "that",
             "of", "for", "with", "to", "in", "on", "by", "at",
             "from", "into", "over", "under", "between"}
_SILENT_E = set("gcv")  # soft consonants carrying silent 'e' (manage, license, approve)
_ES_STEMS = re.compile(r"[sxz]$|[cs]h$|o$")

# E-206: verb/class rule edges (pre-committed, LLM-free regex over unit text).
_VERB_RULES = [
    (re.compile(r"^(.+?)\s+produces\s+(.+)$"), "produces"),
    (re.compile(r"^(.+?)\s+is\s+(?:a|an)\s+(.+)$"), "is_a"),
]


def _capitalize_first(s):
    s = s.strip()
    return s[0].upper() + s[1:] if s else s


def _org_memory(sent, last_org):
    """Deterministic last-org memory: person-marked entities are excluded."""
    s = sent.strip()
    # explicit org patterns win: "CEO of X", "led by CEO X" (capitalized runs only)
    cap = r"[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*"
    m = re.search(r"(?:CEO|CTO|CFO)\s+of\s+(%s)" % cap, s)
    if m:
        return m.group(1).strip()
    m = re.search(r"\blead(?:s|ed)?\s+by\s+(?:CEO\s+)?(%s)" % cap, s)
    if m:
        return m.group(1).strip()
    # sentence-initial proper phrase is an org candidate unless person-marked
    m = re.match(r"^([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)", s)
    if m:
        cand = m.group(1)
        low = cand.lower()
        if low in _SKIP_INITIAL or low.startswith(_PERSON_MARK):
            return last_org
        return cand
    return last_org


def _resolve_anaphora(sent, last_org):
    """Replace leading anaphoric NP with the last org (deterministic)."""
    s = sent.strip()
    low = s.lower()
    if low.startswith("the company") and last_org:
        return last_org + s[len("the company"):]
    if low.startswith("its") and last_org:
        return last_org + "'" + s[len("its"):]  # "Its X" -> "LastOrg' X"
    if low.startswith("it") and last_org:
        return last_org + s[len("it"):]
    return s


def _strip_appositive(sent):
    """'A related firm, Quantum Materials, supplies ...' -> 'Quantum Materials supplies ...'"""
    m = re.match(r"^(?:A|An|The)\s+[A-Za-z]+(?:\s+[A-Za-z]+)?,\s+([A-Z][A-Za-z ]+?),\s+(.+)$",
                 sent.strip())
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return sent


def _gerund_to_finite(clause):
    """'managing warranty claims for Atlas' -> 'manages warranty claims for Atlas'.

    E-212 narrow deterministic gerund -> 3sg-present: strip '-ing', collapse
    doubled consonants (running->run); re-add silent 'e' before the suffix only
    for the {g,c,v} soft-consonant class; else sibilant 'es'. Stems outside the
    class (irregulars, CV-doubles like provide) return None -> verbatim fallback
    (never a broken unit, E-201 control-b lesson).
    """
    m = re.match(r"^(.*?\s)?([A-Za-z]+)ing\s+(.+)$", clause)
    if not m:
        return None
    pre, stem, rest = m.group(1) or "", m.group(2), m.group(3)
    if len(stem) < 2 or stem[-1] in "aeiou":
        return None  # not a regular -ing gerund (going/being/doing...)
    if len(stem) >= 3 and stem[-1] == stem[-2]:
        stem = stem[:-1]  # doubled consonant (running->run)
    if stem[-1] in _SILENT_E:
        stem += "e"
        return f"{pre}{stem}{'es' if _ES_STEMS.search(stem) else 's'} {rest}".strip()
    if _ES_STEMS.search(stem):
        return f"{pre}{stem}es {rest}".strip()
    return None


def _coord_split(sent):
    """E-212: split at the first ' and '/' while ', propagate the left subject
    onto a verb-phrase-headed right clause. Returns None when no valid
    coordinate split (passthrough preserved)."""
    s = sent.strip().rstrip(".")
    m = _COORD_RE.search(s)
    if not m:
        return None
    left, right = s[:m.start()].strip(), s[m.end():].strip()
    sm = re.match(r"^([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)", left)
    if not sm:
        return None
    subject = sm.group(1)
    first_word = right.split()[0]
    if first_word[0].isupper():
        return [left + ".", right + "."]  # own subject NP -> no propagation
    if first_word.lower() in _DET_PREP:
        return None  # object coordination ("X and the Y") -> do not split
    fin = _gerund_to_finite(right)
    if fin is not None:
        return [left + ".", f"{subject} {fin}."]
    return [left + ".", f"{subject} {right}."]


# E-224/E-225: direct-object NP-list + prep-headed complement split — pre-committed,
# docs/experiments/E-224.md, GATE-OK-E-224-8a44aca7 (ONAYLANDI), GATE-OK-E-225-7fa5e4d9 (VERIFIED).
# Applied BEFORE _np_list_split on the passthrough branch of _split_clauses;
# produces UNITS only, NEVER rule edges (control (a) == 0).
_DIRECT_PREP = r"(?:to|for|with|in|at|on|from)"
_DIRECT_2 = re.compile(
    r"^([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+([a-z][a-z-]+)\s+"
    r"(.+?)\s+and\s+(.+?)\s+(%s)\s+(.+)$" % _DIRECT_PREP)
_DIRECT_3 = re.compile(
    r"^([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+([a-z][a-z-]+)\s+"
    r"(.+?)\s*,\s*(.+?)\s*,\s*and\s+(.+?)\s+(%s)\s+(.+)$" % _DIRECT_PREP)


def _direct_nplist_split(sent):
    """E-224/E-225: split a direct-object NP-list ("X <VP> A and B to Y") into one
    subject-anchored clause per member, each keeping the headed complement
    ("... A to Y." / "... B to Y."). Returns None when no match (passthrough
    preserved). Produces UNITS only, NEVER rule edges.

    Deney E-225: docs/experiments/E-225.md (H-225: det_direct_nplist_accuracy >= 0.90)
      -> GATE-OK-E-225-7fa5e4d9 (VERIFIED — 96/100 pooled, Wilson 0.9016 ≥ 0.90;
         rule_edges 0; kod kilidi AÇILDI).
    """
    s = sent.strip().rstrip(".")
    m3 = _DIRECT_3.match(s)
    if m3:
        subj, verb, a, b, c, prep, comp = [g.strip() for g in m3.groups()]
        head = f"{subj} {verb} "
        comp = f"{prep} {comp}"
        return [f"{head}{a} {comp}.", f"{head}{b} {comp}.", f"{head}{c} {comp}."]
    m2 = _DIRECT_2.match(s)
    if m2:
        subj, verb, a, b, prep, comp = [g.strip() for g in m2.groups()]
        head = f"{subj} {verb} "
        comp = f"{prep} {comp}"
        _prep_re = re.compile(r"\b(?:to|for|with|in|at|on|from)\b")
        if any(_prep_re.search(it) for it in (a, b)):
            return None
        return [f"{head}{a} {comp}.", f"{head}{b} {comp}."]
    return None


# E-219: preposition-headed NP-list (object-coordination) split — pre-committed,
# docs/experiments/E-219.md, GATE-OK-E-219-031f3db3 (VERIFIED). Applied FIRST on
# the passthrough branch of _split_clauses; produces UNITS only, NEVER rule
# edges (E-219/E-220/E-221 control (a) == 0 — the metric cannot be inflated).
# E-220/E-221 (GATE-OK-E-220-291f6f1f, GATE-OK-E-221-a1ff139b) extended the
# preposition set with in|at|on|from — the remaining fragment-producing
# prepositions on the production surface (E-201 control (b) 0.00 lesson).
# E-226 (GATE-OK-E-226-ed8a3fe7, VERIFIED) extended the set with
# between|across|through — the last fragment-producing preposition surface
# on the measured corpus; about|over|under documented OUT of scope (no
# natural city-gold surface with the E-208 verb family) in E-226 record.
_NP_HEAD_RE = re.compile(r"^(.*?\s+(?:with|to|for|in|at|on|from|between|across|through)\s+)(.+)$")
_NP_TWO_RE = re.compile(r"^([^,]+?)\s+and\s+([^,]+)$")
_NP_THREE_RE = re.compile(r"^([^,]+)\s*,\s*([^,]+)\s*,\s*and\s+([^,]+)$")


def _np_list_split(sent):
    """Split a preposition-headed NP-list ("with|to|for|in|at|on|from A and
    B[, and C]") into one subject-anchored single-clause unit per list member,
    with left-subject propagation. Returns None when no NP-list matches
    (passthrough preserved). Produces UNITS only, NEVER rule edges.

    Deney E-219: docs/experiments/E-219.md (H-219: det_np_list_accuracy >= 0.90)
      -> GATE-OK-E-219-031f3db3 (VERIFIED — 112/112 pooled, Wilson 0.9668;
         rule_edges 0; flash 8/8 production guarantee preserved).
    Deney E-220: docs/experiments/E-220.md (H-220: det_np_list_prep_accuracy
      >= 0.90) -> GATE-OK-E-220-291f6f1f (0.954, ONAYLANDI but ADVISORY-BLOCK
      — Wilson 0.896 < 0.9; loss is MODEL, not rule: intact 0.78, aile-dışı
      fiiller kilo'da düşük).
    Deney E-221: docs/experiments/E-221.md (H-221: det_np_list_prep_accuracy
      >= 0.90) -> GATE-OK-E-221-a1ff139b (VERIFIED — 171/176 pooled, Wilson
      0.935 ≥ 0.9; kod kilidi AÇILDI; in|at|on|from genişletmesi E-208
      garantili `maintains ... in` ailesinde 0.972, rule_edges 0). Extended
      preposition set to in|at|on|from — closed the fragment surface.
Deney E-224: docs/experiments/E-224.md (H-224: det_direct_nplist_accuracy
      >= 0.90) -> GATE-OK-E-224-8a44aca7 (0.981, ONAYLANDI but ADVISORY-BLOCK
      — Wilson 0.899 < 0.9; 1 stokastik miss, n=52).    Deney E-225: docs/experiments/E-225.md (H-225: det_direct_nplist_accuracy
      >= 0.90) -> GATE-OK-E-225-7fa5e4d9 (VERIFIED — 96/100 pooled, Wilson
      0.9016 ≥ 0.90; rule_edges 0; kod kilidi AÇILDI; direct-object NP-list
      split `_direct_nplist_split` `X <VP> A and B <prep> Y` -> `X <VP> A <prep> Y`
      + `X <VP> B <prep> Y` verb-lossy surface closed).
    Deney E-226: docs/experiments/E-226.md (H-226: det_np_list_prep2_accuracy
      >= 0.90) -> GATE-OK-E-226-ed8a3fe7 (VERIFIED — 167/176 pooled, Wilson
      0.9057 ≥ 0.90; rule_edges 0; kod kilidi AÇILDI; between|across|through
      genişletmesi `_np_list_split`'e entegre — fragment-üreten son edat
      yüzeyi kapandı; about|over|under kapsam dışı, kayıtta belgeli).
    """
    s = sent.strip().rstrip(".")
    m = _NP_HEAD_RE.match(s)
    if not m:
        return None
    pre, tail = m.group(1).strip(), m.group(2).strip()
    items = None
    m3 = _NP_THREE_RE.match(tail)
    if m3 and all(m3.group(i) and m3.group(i).strip() for i in (1, 2, 3)):
        items = [g.strip() for g in m3.groups()]
    else:
        m2 = _NP_TWO_RE.match(tail)
        if m2 and m2.group(1).strip() and m2.group(2).strip():
            items = [g.strip() for g in m2.groups()]
    if not items or len(items) < 2:
        return None
    if any("which" in it or "," in it for it in items):
        return None
    # A list member headed by a lowercase (finite) verb is CLAUSE coordination,
    # not an NP-list ("... with A and licenses B to C") -> E-212 owns that
    # surface, not this split (E-212 regression lock).
    if any(it.split()[0].islower() for it in items):
        return None
    # E-212 coordinate-clause guard (extended prep set): "in Denver and Quantum
    # Materials maintains a warehouse in Denver" — the right member is a NEW
    # subject + finite verb, so its 3rd word (after a 2-word org NP) is a
    # lower-case verb; a bare NP ("Boston") or 2-word NP ("Vertex Robotics")
    # has no 3rd word. Reject the former so E-212's two-subject coordinate
    # clause stays untouched.
    if any(len(it.split()) >= 3 and it.split()[2].islower() for it in items):
        return None
    return [f"{pre} {o}." for o in items]


def _split_long_subject(sent):
    """E-217/E-218 long-subject decomposition (relative-clause split + subject
    propagation, participial modifier strip, embedded-genitive anchoring,
    leading-modifier strip). Units ONLY, never rule edges — E-218 control (a)
    == 0, pre-committed docs/experiments/E-218.md, GATE-OK-E-218-08fb2b9d.
    Returns None when no rule matches (passthrough preserved).
    """
    s = sent.strip().rstrip(".")
    # R1: relative-clause split + subject propagation
    #   "X, which <rel VP>, <main VP>." -> ["X <rel VP>.", "X <main VP>."]
    m = re.match(r"^(.+?),\s+which\s+(.+?),\s+(.+)$", s)
    if m:
        subj, rel, main = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        return [f"{subj} {rel}.", f"{subj} {main}."]
    # R2: participial modifier strip (comma-set-off participial phrase)
    #   "X, headquartered in Denver, <main VP>." -> ["X <main VP>."]
    m = re.match(r"^(.+?),\s+(?:headquartered|based|located|registered|incorporated)"
                 r"\s+(?:in|at|on|near)\s+[^,]+,\s+(.+)$", s)
    if m:
        return [f"{m.group(1).strip()} {m.group(2).strip()}."]
    # R3: embedded-subject genitive -> org anchoring
    #   "The battery division of Quantum Materials <VP>." -> ["Quantum Materials <VP>."]
    m = re.match(r"^The\s+(.+?)\s+of\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(.+)$", s)
    if m:
        return [f"{m.group(2).strip()} {m.group(3).strip()}."]
    # R4: leading-modifier strip (premodifier before the org subject)
    #   "The Austin-based robotics firm Nova Dynamics <VP>." -> ["Nova Dynamics <VP>."]
    #   Narrow deterministic pattern: "The <X>-based <noun> <noun>? <ORG> <VP>".
    m = re.match(r"^The\s+[A-Za-z]+-based\s+[a-z]+(?:\s+[a-z]+)?\s+"
                 r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(.+)$", s)
    if m:
        return [f"{m.group(1).strip()} {m.group(2).strip()}."]
    return None


def _split_clauses(sent):
    """Deterministic clause decomposition of the known dense patterns.

    Returns list of self-contained, subject-anchored units (active voice).
    Rules 1-6 (copular-temporal, career timeline, possessive-product, temporal
    recursion, passive) are tried first, verbatim (E-204/E-206). Only the
    passthrough branch additionally tries the E-212 coordinate split.
    """
    s = sent.strip()
    prod = "|".join(_PRODUCT_NOUNS)

    # (1) copular + temporal appositive: "X is a Y founded in Z."
    m = re.match(r"^(.+?)\s+is\s+(a|an)\s+([^,.]+?)\s+(%s)\s+in\s+(\d{4})\.?$"
                 % "|".join(_TEMP_VERBS[:4]), s)
    if m:
        x, det, y, verb, year = m.groups()
        return [f"{x} is {det} {y}.", f"{x} was {verb} in {year}."]

    # (2) "X has been the ROLE of Y since year" (career timeline)
    m = re.match(r"^(.+?)\s+has been\s+(the\s+)?([A-Za-z]+?)\s+of\s+(.+?)\s+since\s+(\d{4})\.?$", s)
    if m:
        x, the, role, y, year = m.groups()
        the = the or "the "
        return [f"{x} is {the}{role} of {y}.", f"{x} has been {the}{role} since {year}."]

    # (3) possessive-product + temporal appositive:
    #     "X' flagship product is Y, released in Z." (apostrophe, optional s)
    m = re.match(r"^(.+?)'s?\s+(%s)\s+is\s+(.+?),\s+(%s)\s+in\s+(\d{4})\.?$"
                 % (prod, "|".join(_TEMP_VERBS)), s)
    if m:
        x, _np, y, verb, year = m.groups()
        return [f"{x} produces {y}.", f"{_capitalize_first(y)} was {verb} in {year}."]

    # (4) "X was founded in Y and <clause2>" (coordinated clauses; recurse)
    m = re.match(r"^(.+?)\s+was\s+(founded|established|incorporated)\s+in\s+(\d{4})\s+and\s+(.+)$", s)
    if m:
        x, verb, year, rest = m.groups()
        return [f"{x} was {verb} in {year}."] + _split_clauses(f"{x} {rest}")

    # (5) possessive-product alone: "X' flagship product is Y."
    m = re.match(r"^(.+?)'s?\s+(%s)\s+is\s+(.+)$" % prod, s)
    if m:
        x, _np, y = m.groups()
        return [f"{x} produces {y}."]

    # (6) passive -> active (subject flip): "X is led by CEO Y." -> "Y leads X."
    m = re.match(r"^(.+?)\s+is\s+(led|headed|run)\s+by\s+(?:CEO\s+|President\s+|CTO\s+)?(.+?)\.?$", s)
    if m:
        x, vb, y = m.groups()
        return [f"{_capitalize_first(y)} {_PASSIVE_VERB[vb]} {x}."]

    # E-224/E-225: direct-object NP-list split ("X <VP> A and B to Y"), tried
    # FIRST on the passthrough branch — _coord_split sees the 'and' and emits
    # verb-lossy units ("X control units to Y").
    parts = _direct_nplist_split(s)
    if parts is not None:
        return parts
    # E-219: NP-list (object-coordination) split, tried FIRST on the passthrough
    # branch — _coord_split sees the 'and' and, the right head being an
    # upper-case name, takes the "own subject" branch and emits a subject-less
    # fragment "B." (E-201 control (b) 0.00 lesson). Preposition-headed lists
    # are split deterministically into one single-clause unit per member.
    parts = _np_list_split(s)
    if parts is not None:
        return parts
    # E-212: no production rule matched -> try the coordinate-clause split
    # (subject propagation). If that yields nothing either, try the E-217/E-218
    # long-subject extension (relative-clause split, participial strip,
    # embedded-genitive anchoring, leading-modifier strip). Only if BOTH yield
    # nothing does the sentence pass through unchanged.
    parts = _coord_split(s)
    if parts is not None:
        return parts
    parts = _split_long_subject(s)
    return parts if parts is not None else [s]  # passthrough (anaphora/appositive already applied)


def _rule_edges(sent):
    """Deterministic temporal edges from one processed sentence (LLM-free).

    Cue attribution heuristic: 'founded/... in Y' and 'since Y' attach to the
    sentence-initial subject; 'released in Y' attaches to the possessive-product
    object. (E-127/E-174 pattern.)
    """
    edges = []
    s = sent.strip()

    m = re.search(r"\b(founded|established|incorporated)\s+in\s+(\d{4})", s)
    if m:
        sm = re.match(r"^(.+?)\s+(?:was|is|has been)", s)
        if sm:
            edges.append((sm.group(1).strip(), "founded_in", m.group(2)))

    m = re.search(r"\b(released|launched|introduced)\s+in\s+(\d{4})", s)
    if m:
        prod = "|".join(_PRODUCT_NOUNS)
        pm = re.match(r"^(.+?)'s?\s+(?:%s)\s+is\s+(.+?),\s+%s\s+in\s+%s\.?$"
                      % (prod, m.group(1), m.group(2)), s)
        if pm:
            edges.append((pm.group(2).strip(), "released_in", m.group(2)))

    m = re.search(r"\bsince\s+(\d{4})", s)
    if m:
        sm = re.match(r"^(.+?)\s+has been", s)
        if sm:
            edges.append((sm.group(1).strip(), "ceo_since", m.group(1)))

    # E-233: temporal CHANGE surfaces (pre-committed in docs/experiments/E-233.md).
    # "X was CEO of Y until Z" / "X became CEO of Y in Z" -> (X, "CEO", Y) role
    # edge where X = the person BEFORE the role word. valid_at is parsed
    # downstream by `_parse_valid_at` ("until Z" / "in Z" — E-127/E-174 grammar);
    # the rule edge carries only the role pair, which `llm_short_unit_temporal`'s
    # role normalization (E-128) turns into (company, "CEO", person). The
    # TemporalResolver then SUPERSEDES the until-Z edge by the in-Z edge ->
    # "stale fact never current" (amiral-gemi report).
    m = re.search(r"^(.+?)\s+was\s+(?:the\s+)?(?:CEO|CTO|CFO)\s+of\s+(.+?)\s+until\s+(\d{4})", s)
    if m:
        edges.append((m.group(1).strip(), "CEO", m.group(2).strip()))
    m = re.search(r"^(.+?)\s+became\s+(?:the\s+)?(?:CEO|CTO|CFO)\s+of\s+(.+?)\s+in\s+(\d{4})", s)
    if m:
        edges.append((m.group(1).strip(), "CEO", m.group(2).strip()))

    return edges


def _verb_rule_edges(units):
    """E-206/E-222: deterministic verb/class edges from unit text (no LLM).

    Pre-committed patterns: `X produces Y` -> (X, "produces", Y);
    `X is a Y` -> (X, "is_a", Y). The object may carry the sentence-final
    period; it is stripped so downstream normalizers match. E-222 (GATE-OK-
    E-222-, docs/experiments/E-222.md) splits a COORDINATED compound object
    into one edge per member: `X produces the A and the B` -> two produces
    edges, `A, B, and C` -> three. Single objects stay single.
    """
    edges = []
    for u in units:
        s = u.strip()
        for rx, pred in _VERB_RULES:
            m = rx.match(s)
            if m:
                subj = m.group(1).strip()
                for obj in _split_compound_obj(m.group(2)):
                    edges.append((subj, pred, obj.rstrip(".")))
    return edges


# E-222: split a coordinated compound object into its list members (no LLM).
_AND_RE = re.compile(r"^(.*?)\s+and\s+(.+)$")


def _split_compound_obj(obj):
    """Return member objects for a coordinated compound ("the A and the B",
    "A, B, and C"). Returns [obj] when not a clear 2/3-member list."""
    obj = obj.strip()
    parts = [p.strip() for p in re.split(r",\s+", obj)]
    if len(parts) >= 3:
        last = parts[-1]
        if last.startswith("and "):
            parts[-1] = last[4:].strip()
        elif " and " in last:
            a, b = last.split(" and ", 1)
            parts[-1] = a.strip()
            parts.append(b.strip())
        return [p for p in parts if p]
    m = _AND_RE.match(obj)
    if m and not obj.startswith("and "):
        a, b = m.group(1).strip(), m.group(2).strip()
        if a and b:
            return [a, b]
    return [obj]


def unitize(sentences):
    """Document -> (units, rule_edges). Fully deterministic.

    rule_edges = temporal edges (founded_in / released_in / ceo_since) UNION
    verb/class edges (produces / is_a) — the full E-206 rule set.
    """
    units = []
    temporal_edges = []
    last_org = None
    for raw in sentences:
        last_org = _org_memory(raw, last_org)
        sent = _resolve_anaphora(raw, last_org)
        sent = _strip_appositive(sent)
        temporal_edges.extend(_rule_edges(sent))
        units.extend(_split_clauses(sent))
    return units, temporal_edges + _verb_rule_edges(units)


if __name__ == "__main__":
    SENTENCES = [
        "Nova Dynamics is a robotics company founded in 2018.",
        "The company is headquartered in Austin, Texas.",
        "Dr. Lena Ortiz has been the CEO of Nova Dynamics since 2021.",
        "Its flagship product is the Atlas robotic arm, released in 2022.",
        "A related firm, Quantum Materials, supplies batteries to Nova Dynamics.",
        "Quantum Materials was founded in 2015 and is led by CEO Rajesh Patel.",
    ]
    ORACLE_UNITS = [
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
    EXP_RULE_EDGES = {
        ("nova_dynamics", "2018"),
        ("lena_ortiz", "2021"),
        ("atlas", "2022"),
        ("quantum_materials", "2015"),
        ("nova_dynamics", "atlas"),          # produces (E-206)
        ("nova_dynamics", "robotics_company"),  # is_a (E-206)
    }
    units, edges = unitize(SENTENCES)
    print("== D-1 deterministic units ==")
    for u in units:
        print(f"  {u}")
    print(f"rule_fidelity={len(set(units) & set(ORACLE_UNITS))}/{len(ORACLE_UNITS)}")
    print(f"  units == oracle: {units == ORACLE_UNITS}")
    print("== rule-based edges ==")
    for e in edges:
        print(f"  {e}")
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower().strip()).strip().replace(" ", "_")
    edge_so = {(norm(s), norm(o)) for (s, _p, o) in edges}
    print(f"rule_edge_recovery={len(edge_so & EXP_RULE_EDGES)}/{len(EXP_RULE_EDGES)} "
          f"(expected pairs {sorted(EXP_RULE_EDGES)})")

    # E-212: coordinate split + subject propagation (pre-committed, E-212.md).
    # Regression lock: exactly the 9 single-clause composite units, 0 rule edges.
    E212_SENTENCES = [
        "Nova Dynamics, the robotics firm, negotiates supply agreements with Quantum Materials.",
        "Quantum Materials coordinates delivery logistics with Nova Dynamics and licenses battery patents to Meridian Labs.",
        "Meridian Labs provides laboratory services to Quantum Materials while managing warranty claims for Atlas.",
        "Atlas generates maintenance reports for Meridian Labs and streams telemetry to Quantum Materials.",
        "Nova Dynamics maintains a joint testing facility in Denver and Quantum Materials maintains a warehouse in Denver.",
    ]
    E212_EXPECTED = [
        "Nova Dynamics, the robotics firm, negotiates supply agreements with Quantum Materials.",
        "Quantum Materials coordinates delivery logistics with Nova Dynamics.",
        "Quantum Materials licenses battery patents to Meridian Labs.",
        "Meridian Labs provides laboratory services to Quantum Materials.",
        "Meridian Labs manages warranty claims for Atlas.",
        "Atlas generates maintenance reports for Meridian Labs.",
        "Atlas streams telemetry to Quantum Materials.",
        "Nova Dynamics maintains a joint testing facility in Denver.",
        "Quantum Materials maintains a warehouse in Denver.",
    ]
    u212, e212 = unitize(E212_SENTENCES)
    print("== E-212 coordinate split + subject propagation ==")
    for u in u212:
        print(f"  {u}")
    print(f"E-212 units == expected: {u212 == E212_EXPECTED} ({len(u212)}/{len(E212_EXPECTED)})")
    print(f"E-212 rule_edges: {len(e212)} (MUST be 0 — control (a), E-015)")
    assert u212 == E212_EXPECTED, "E-212 coordinate split produced wrong units"
    assert not e212, f"E-212 must emit 0 rule edges, got {len(e212)}"

    # E-219: NP-list (object-coordination) split (pre-committed, E-219.md).
    # Regression lock: preposition-headed lists -> one unit per member, 0 rules.
    E219_SENTENCES = [
        "Helios Systems negotiates supply agreements with Vertex Robotics and Northwind Labs.",
        "Albion Energy negotiates supply agreements with Helios Systems, Vertex Robotics, and Northwind Labs.",
    ]
    E219_EXPECTED = [
        "Helios Systems negotiates supply agreements with Vertex Robotics.",
        "Helios Systems negotiates supply agreements with Northwind Labs.",
        "Albion Energy negotiates supply agreements with Helios Systems.",
        "Albion Energy negotiates supply agreements with Vertex Robotics.",
        "Albion Energy negotiates supply agreements with Northwind Labs.",
    ]
    u219, e219 = unitize(E219_SENTENCES)
    print("== E-219 NP-list (object-coordination) split ==")
    for u in u219:
        print(f"  {u}")
    print(f"E-219 units == expected: {u219 == E219_EXPECTED} ({len(u219)}/{len(E219_EXPECTED)})")
    print(f"E-219 rule_edges: {len(e219)} (MUST be 0 — control (a), E-015)")
    assert u219 == E219_EXPECTED, "E-219 NP-list split produced wrong units"
    assert not e219, f"E-219 must emit 0 rule edges, got {len(e219)}"

    # E-225: direct-object NP-list split (pre-committed, E-225.md, GATE-OK-E-225-7fa5e4d9).
    # Regression lock: direct-object NP-list + prep complement -> one unit per member + complement, 0 rules.
    E225_SENTENCES = [
        "Helios Systems supplies batteries and control units to Quantum Materials.",
        "Quantum Materials licenses its solid-state cells and sodium packs to Helios Systems.",
    ]
    E225_EXPECTED = [
        "Helios Systems supplies batteries to Quantum Materials.",
        "Helios Systems supplies control units to Quantum Materials.",
        "Quantum Materials licenses its solid-state cells to Helios Systems.",
        "Quantum Materials licenses sodium packs to Helios Systems.",
    ]
    u225, e225 = unitize(E225_SENTENCES)
    print("== E-225 direct-object NP-list split ==")
    for u in u225:
        print(f"  {u}")
    print(f"E-225 units == expected: {u225 == E225_EXPECTED} ({len(u225)}/{len(E225_EXPECTED)})")
    print(f"E-225 rule_edges: {len(e225)} (MUST be 0 — control (a), E-015)")
    assert u225 == E225_EXPECTED, "E-225 direct-object NP-list split produced wrong units"
    assert not e225, f"E-225 must emit 0 rule edges, got {len(e225)}"
