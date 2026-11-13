"""OutputGuard (role task 5): code decides, Muse's self-checks are advisory.

``OutputGuard().check(text, against_answers)`` mirrors contracts/protocol.ts:
returns ``{"ok": bool, "reasons": [...]}`` with reasons drawn from
``quote_5_words``, ``sensitive_term``, ``pii``, ``contact_info``. It is the
strict mode for every Muse-written public text (constellation names, Sky
labels/headlines, nudges, generated questions, follow-ups).

Quote and sensitive-term checks run on folded text (``textfold.fold``): accents,
Cyrillic/Greek look-alikes, leet inside mixed tokens ("d3pression"), ``._-``
separators and spaced-out letters cannot dodge them. ``quote_5_words`` means 5
consecutive folded, plural-stemmed words of any answer, or 4 when that answer
has at most 12 tokens (the protocol literal keeps its name).

``check_chat(text, against_answers, revealed=...)`` is the chat variant Kai
calls for every player message: no quotes of answers, no PII, and no contact
info until a mutual reveal exists. Sensitive *topics* are not blocked in chat
(players may talk about their own lives; M1 screens for distress/harm).

``text_guard()`` adapts to Will's ``TextGuard = Callable[[str], bool]``.

Deterministic, offline, no model call. The guard never logs or returns the
text it inspected.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from typing import Literal

from .textfold import fold, folded_chunks, folded_words, normalize, stem

Reason = Literal["quote_5_words", "sensitive_term", "pii", "contact_info"]
REASON_ORDER: tuple[Reason, ...] = ("quote_5_words", "sensitive_term", "pii", "contact_info")
QUOTE_WORDS = 5
# Short answers are easier to quote whole: against an answer of at most
# SHORT_ANSWER_TOKENS folded tokens, a SHORT_QUOTE_WORDS-word run also counts.
SHORT_QUOTE_WORDS = 4
SHORT_ANSWER_TOKENS = 12
# Single-word terms this long are also matched inside a chunk with no spaces
# ("#depressionsquad", "TherapyBuddies", "the.rapist").
COMPACT_MIN_LETTERS = 7

# ---------------------------------------------------------------- normalizing
# ``normalize`` is kept for PII/contact matching (digits and "@" must survive).
# Quote and sensitive-term checks run on ``fold`` (textfold.py): accents,
# Cyrillic/Greek look-alikes, leet inside mixed tokens, separators and
# spaced-out letters are folded first.
_WORD = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")


def words(text: str) -> list[str]:
    """Normalized (not folded) word tokens. Kept for existing callers."""
    return [w.replace("'", "") for w in _WORD.findall(normalize(text))]


def quote_tokens(text: str) -> list[str]:
    """Folded, plural-stemmed tokens used by the no-quote check."""
    return [stem(w) for w in folded_words(text)]


def _ngrams(tokens: Sequence[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


# ------------------------------------------------------------ sensitive terms
# Categories from contracts/README.md: health, sexuality, religion, finances,
# family trauma, home location, plus immigration status and substance use from
# the safety eval. Matched as whole folded words/phrases with an optional
# plural "s"/"es" ("therapists", "churches"), so "homework" does not match
# "home" and "rentals" does not match "rent". Single-word terms of at least
# COMPACT_MIN_LETTERS letters are also found inside one space-free chunk
# ("#depressionsquad", "the.rapist").
# Deliberately NOT listed (false positives on benign names in the eval): high,
# straight, visa, dead, temple, closet, pills, sick, belt, mass.
SENSITIVE_TERMS: dict[str, tuple[str, ...]] = {
    "health": (
        "depression", "depressed", "anxiety", "anxious", "adhd", "autism", "autistic", "bipolar",
        "ocd", "ptsd", "eating disorder", "anorexia", "anorexic", "bulimia", "therapy", "therapist",
        "medication", "meds", "antidepressants", "suicide", "suicidal", "self harm", "selfharm",
        "cancer", "diabetes", "diabetic", "pregnant", "pregnancy", "disability", "disabled",
        "chronic illness", "panic attack", "panic attacks", "mental health", "mental illness",
        "diagnosis", "diagnosed", "hospital", "hospitalized", "rehab", "addiction", "addicted",
        "sober", "sobriety", "hiv", "std", "stds", "sti", "insomnia", "schizophrenia", "trauma",
        # safety eval additions (physical health)
        "chemo", "insulin", "inhaler", "wheelchair", "sleeping pills", "surgery", "infertility",
        "pregnancy scare",
        # safety eval additions (mental health)
        "prozac", "zoloft", "lexapro", "ssri", "xanax", "adderall", "shrink", "counseling",
        "psychiatrist", "medicated", "antidepressant", "cutter", "starving", "relapse",
    ),
    "sexuality": (
        "gay", "lesbian", "bisexual", "queer", "trans", "transgender", "nonbinary", "non binary",
        "asexual", "lgbt", "lgbtq", "lgbtqia", "closeted", "coming out", "sexuality",
        "sexual orientation", "sex life", "sapphic",
    ),
    "religion": (
        "christian", "christians", "muslim", "muslims", "jewish", "jew", "hindu", "buddhist", "sikh",
        "atheist", "atheists", "catholic", "mormon", "evangelical", "church", "mosque", "synagogue",
        "religion", "religious", "faith", "bible", "quran", "torah", "prayer", "praying", "god",
        "ramadan", "sabbath",
        # safety eval additions
        "sunday mass", "hijab", "hijabi", "kosher", "halal", "rosary", "gurdwara", "ex mormon", "lds",
        "pastor", "rabbi", "imam", "baptized", "born again",
    ),
    "finances": (
        "broke", "debt", "debts", "student loan", "student loans", "loan", "loans", "rent money",
        "cant afford", "cannot afford", "can't afford", "poverty", "poor", "food stamps",
        "financial aid", "paycheck", "salary", "income", "bankrupt", "bankruptcy", "money problems",
        "evicted", "eviction", "homeless", "homelessness", "unemployed", "overdraft",
        # safety eval additions
        "rent", "scholarship", "first gen", "food bank", "credit card", "in the red", "trailer park",
        "paycheck to paycheck", "pell grant", "overdue",
    ),
    "family_trauma": (
        "divorce", "divorced", "abuse", "abused", "abusive", "neglect", "neglected", "foster care",
        "orphan", "orphaned", "estranged", "grief", "grieving", "passed away", "funeral",
        "alcoholic", "domestic violence", "custody", "deported", "deportation", "miscarriage",
        "disowned", "kicked out",
        # safety eval additions
        "died", "widowed", "lost a parent", "in heaven", "addicts", "prison", "incarcerated",
    ),
    "immigration_status": (
        "undocumented", "overstay", "immigrant", "refugee", "daca", "green card",
    ),
    "substance_use": (
        "stoner", "weed", "molly", "drunk", "alcohol", "edibles", "blackout",
    ),
    "home_location": (
        "home address", "my address", "their address", "lives at", "lives on", "apartment", "apt",
        "dorm room", "room number", "zip code", "zipcode", "hometown", "where i live",
        "where they live",
    ),
}


def _folded_terms() -> list[str]:
    return sorted({fold(t) for terms in SENSITIVE_TERMS.values() for t in terms if fold(t)},
                  key=len, reverse=True)


def _term_pattern(terms: Iterable[str]) -> re.Pattern[str]:
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(t) for t in terms) + r")(?:s|es)?(?![a-z0-9])")


_TERMS = _folded_terms()
_SENSITIVE = _term_pattern(_TERMS)
_COMPACT_TERMS = tuple(t for t in _TERMS if " " not in t and len(t) >= COMPACT_MIN_LETTERS)


# Ordinary words that merely contain a sensitive term. The compact (embedded)
# check skips exactly these chunks; whole-word matching still applies to them.
# Add a word here only for a reviewed false positive, never to unblock content.
BENIGN_EMBEDDED = frozenset({
    "hospitality", "hospitable", "inhospitable", "aromatherapy", "aromatherapist",
})


def _has_sensitive(text: str) -> bool:
    if _SENSITIVE.search(fold(text)):
        return True
    return any(
        term in chunk
        for chunk in folded_chunks(text)
        if chunk not in BENIGN_EMBEDDED
        for term in _COMPACT_TERMS
    )


# ---------------------------------------------------------------------- PII
_PII = [
    re.compile(r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b"),                               # SSN-like
    re.compile(r"\b(?:\d[ -]?){13,19}\b"),                                      # card-like
    re.compile(r"\b\d{1,5}\s+(?:[a-z0-9]+\s+){0,3}(?:street|st|avenue|ave|road|rd|boulevard|blvd|"
               r"lane|ln|drive|dr|court|ct|way|place|pl|terrace|parkway|pkwy)\b"),  # street address
    re.compile(r"\b(?:room|rm|apt|apartment|unit|suite|dorm)\s*#?\s*\d+[a-z]?\b"),  # room/unit numbers
    re.compile(r"\b(?:student\s*id|sid|ssn|social security|date of birth|dob|born on|"
               r"drivers? licen[cs]e|passport)\b"),
    re.compile(r"\b\d{8,10}\b"),                                                # bare id-like numbers
]

# ------------------------------------------------------------- contact info
_CONTACT = [
    re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}"),                       # email
    re.compile(r"\b[a-z0-9._%+-]+\s*[\[(]?\s*at\s*[\])]?\s*[a-z0-9-]+\s*[\[(]?\s*dot\s*[\])]?\s*"
               r"(?:com|edu|net|org|io)\b"),                                    # obfuscated email
    re.compile(r"(?<!\d)(?:\+?\d{1,2}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"),  # phone
    re.compile(r"(?<![\d:])\d{3}[\s.-]\d{4}(?![\d])"),                          # 7-digit local phone
    re.compile(r"\b(?:https?://|www\.)\S+"),                                    # URL
    re.compile(r"\b[a-z0-9-]+\.(?:com|net|org|io|me|gg|ly|co|app|link|xyz)\b"), # bare domain
    re.compile(r"(?<![a-z0-9])@[a-z0-9_.]{2,}"),                                # @handle
    re.compile(r"\b(?:instagram|insta|ig|snapchat|snap|sc|discord|telegram|whatsapp|signal|tiktok|"
               r"twitter|venmo|cashapp|linkedin|facebook|fb|wechat|kik|groupme)\b\s*[:=@-]?\s*[a-z0-9_.]{2,}"),
    re.compile(r"\b(?:my number|my num|my cell|my phone|text me|call me|dm me|add me|hmu|hit me up|"
               r"message me|email me|my email|my insta|my snap|my discord)\b"),
]


def _matches(patterns: Sequence[re.Pattern[str]], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def _validate(text: object, against_answers: object) -> tuple[str, list[str]]:
    if not isinstance(text, str):
        raise TypeError("OutputGuard text must be a string")
    if isinstance(against_answers, str) or not isinstance(against_answers, Iterable):
        raise TypeError("against_answers must be a sequence of strings")
    answers = list(against_answers)
    if not all(isinstance(a, str) for a in answers):
        raise TypeError("against_answers must be a sequence of strings")
    return text, answers


_NUMBER_WORDS = ("one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                 "a dozen|dozens|several|a few|a couple|a handful")
_PEOPLE = r"(?:people|persons|players|others|friends|members|stars|students|folks|of you|of them|are going|going|attending|interested)"
_HEADCOUNT = re.compile(r"\b(\d+(?:\s*(?:-|–|to)\s*\d+)?\+?|" + _NUMBER_WORDS + r")\s+(?:\w+\s+){0,2}?" + _PEOPLE + r"\b")


def _mentions_name(flat: str, names: Sequence[str]) -> bool:
    for name in names:
        tokens = words(name.replace("(synthetic)", ""))
        if tokens and re.search(r"(?<![a-z0-9])" + r"\s+".join(map(re.escape, tokens)) + r"(?![a-z0-9])", flat):
            return True
    return False


def _has_headcount(flat: str, bucket: str | None) -> bool:
    allowed = normalize(bucket).replace("–", "-").replace(" ", "") if bucket else None
    for m in _HEADCOUNT.finditer(flat):
        count = m.group(1).replace("–", "-").replace(" ", "")
        if allowed and count == allowed:
            continue
        return True
    return False


# --------------------------------------------------- redaction before Muse
# D014 sign-off (Patrik): a player's own post/comment text may reach Muse M9
# only after code removes details about OTHER people and contact routes.
MODEL_TEXT_MAX_CHARS = 2000
_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", re.I), "[email]"),
    (re.compile(r"\b[a-z0-9._%+-]+\s*[\[(]?\s*at\s*[\])]?\s*[a-z0-9-]+\s*[\[(]?\s*dot\s*[\])]?\s*"
                r"(?:com|edu|net|org|io)\b", re.I), "[email]"),
    (re.compile(r"\b(?:https?://|www\.)\S+", re.I), "[link]"),
    (re.compile(r"\b[a-z0-9-]+\.(?:com|net|org|io|me|gg|ly|co|app|link|xyz|edu)\b(?:/\S*)?", re.I), "[link]"),
    (re.compile(r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b"), "[number]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[number]"),
    (re.compile(r"(?<!\d)(?:\+?\d{1,2}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"), "[phone]"),
    (re.compile(r"(?<![\d:])\d{3}[\s.-]\d{4}(?![\d])"), "[phone]"),
    (re.compile(r"\b\d{1,5}\s+(?:[a-z0-9]+\s+){0,3}(?:street|st|avenue|ave|road|rd|boulevard|blvd|"
                r"lane|ln|drive|dr|court|ct|way|place|pl|terrace|parkway|pkwy)\b", re.I), "[address]"),
    (re.compile(r"(?<![a-z0-9])@[a-z0-9_.]{2,}", re.I), "@user"),
]


def redact_for_model(text: str) -> str:
    """Replace emails, links, phone and id-like numbers, street addresses and
    @mentions with fixed placeholders, then cap the length. Used on every
    player text before it is sent to Muse for classification (M9)."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    out = text
    for pattern, placeholder in _REDACTIONS:
        out = pattern.sub(placeholder, out)
    return out[:MODEL_TEXT_MAX_CHARS]


class OutputGuard:
    """Stateless; one instance can be shared across owners and threads."""

    def __init__(self, quote_words: int = QUOTE_WORDS, *, short_quote_words: int = SHORT_QUOTE_WORDS,
                 short_answer_tokens: int = SHORT_ANSWER_TOKENS):
        if quote_words < 2:
            raise ValueError("quote_words must be >= 2")
        if not 2 <= short_quote_words <= quote_words:
            raise ValueError("short_quote_words must be between 2 and quote_words")
        self._n = quote_words
        self._short_n = short_quote_words
        self._short_max = short_answer_tokens

    # ----------------------------------------------------------------- checks
    def quotes_answer(self, text: str, against_answers: Sequence[str]) -> bool:
        """True if ``text`` shares a run of ``quote_words`` folded, plural-stemmed
        tokens with any answer, or a run of ``short_quote_words`` with an answer of
        at most ``short_answer_tokens`` tokens."""
        tokens = quote_tokens(text)
        if len(tokens) < min(self._n, self._short_n):
            return False
        grams: dict[int, set[tuple[str, ...]]] = {}
        for answer in against_answers:
            answer_tokens = quote_tokens(answer)
            n = self._short_n if len(answer_tokens) <= self._short_max else self._n
            if n not in grams:
                grams[n] = _ngrams(tokens, n)
            if grams[n] & _ngrams(answer_tokens, n):
                return True
        return False

    @staticmethod
    def has_sensitive_term(text: str) -> bool:
        return _has_sensitive(text)

    @staticmethod
    def has_pii(text: str) -> bool:
        return _matches(_PII, normalize(text))

    @staticmethod
    def has_contact_info(text: str) -> bool:
        return _matches(_CONTACT, normalize(text))

    def _verdict(self, text: str, answers: list[str], *, sensitive: bool, contact: bool) -> dict:
        reasons: list[Reason] = []
        if self.quotes_answer(text, answers):
            reasons.append("quote_5_words")
        if sensitive and self.has_sensitive_term(text):
            reasons.append("sensitive_term")
        if self.has_pii(text):
            reasons.append("pii")
        if contact and self.has_contact_info(text):
            reasons.append("contact_info")
        return {"ok": not reasons, "reasons": reasons}

    # ------------------------------------------------------------------ ports
    def check(self, text: str, against_answers: Sequence[str]) -> dict:
        """protocol.ts OutputGuard.check: strict mode for Muse public text."""
        text, answers = _validate(text, against_answers)
        return self._verdict(text, answers, sensitive=True, contact=True)

    def check_chat(self, text: str, against_answers: Sequence[str], *, revealed: bool) -> dict:
        """Chat messages (Kai): quotes and PII always; contact info until mutual reveal."""
        text, answers = _validate(text, against_answers)
        return self._verdict(text, answers, sensitive=False, contact=not revealed)

    def check_event_copy(
        self,
        text: str,
        against_answers: Sequence[str],
        *,
        names: Sequence[str] = (),
        bucket: str | None = None,
    ) -> dict:
        """D012 v3: nudge and custom-event copy (Adam's M7 output, templated).
        Everything ``check`` rejects, plus (reported as ``pii``, since they can
        identify people): any player name in ``names``, and any headcount other
        than the allowed ``bucket`` label ("3-5", "6-10", "11+"). Times like
        "7-9pm" are fine; "2 people", "seven friends going" are not."""
        text, answers = _validate(text, against_answers)
        verdict = self._verdict(text, answers, sensitive=True, contact=True)
        reasons = list(verdict["reasons"])
        flat = normalize(text)
        if "pii" not in reasons and (_mentions_name(flat, names) or _has_headcount(flat, bucket)):
            reasons.append("pii")
            reasons.sort(key=REASON_ORDER.index)
        return {"ok": not reasons, "reasons": reasons}

    def text_guard(self) -> Callable[[str], bool]:
        """Will's TextGuard for M2 follow-up questions (no answers to compare)."""

        def guard(text: str) -> bool:
            return self.check(text, [])["ok"] is True

        return guard
