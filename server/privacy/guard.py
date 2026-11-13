"""OutputGuard (role task 5): code decides, Muse's self-checks are advisory.

``OutputGuard().check(text, against_answers)`` mirrors contracts/protocol.ts:
returns ``{"ok": bool, "reasons": [...]}`` with reasons drawn from
``quote_5_words``, ``sensitive_term``, ``pii``, ``contact_info``. It is the
strict mode for every Muse-written public text (constellation names, Sky
labels/headlines, nudges, generated questions, follow-ups).

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
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from typing import Literal

Reason = Literal["quote_5_words", "sensitive_term", "pii", "contact_info"]
REASON_ORDER: tuple[Reason, ...] = ("quote_5_words", "sensitive_term", "pii", "contact_info")
QUOTE_WORDS = 5

# ---------------------------------------------------------------- normalizing
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'"})
_WORD = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")


def normalize(text: str) -> str:
    """NFKC, drop invisible format chars (zero-width etc.), lowercase, unify apostrophes."""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) not in {"Cf", "Cc"} or ch in "\n\t ")
    return text.translate(_APOSTROPHES).lower()


def words(text: str) -> list[str]:
    return [w.replace("'", "") for w in _WORD.findall(normalize(text))]


def _ngrams(tokens: Sequence[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


# ------------------------------------------------------------ sensitive terms
# Categories from contracts/README.md: health, sexuality, religion, finances,
# family trauma, home location. Matched as whole words/phrases after
# normalization, so "therapist" is caught but "the rapist"-style splits are
# not invented and "homework" does not match "home".
SENSITIVE_TERMS: dict[str, tuple[str, ...]] = {
    "health": (
        "depression", "depressed", "anxiety", "anxious", "adhd", "autism", "autistic", "bipolar",
        "ocd", "ptsd", "eating disorder", "anorexia", "anorexic", "bulimia", "therapy", "therapist",
        "medication", "meds", "antidepressants", "suicide", "suicidal", "self harm", "selfharm",
        "cancer", "diabetes", "diabetic", "pregnant", "pregnancy", "disability", "disabled",
        "chronic illness", "panic attack", "panic attacks", "mental health", "mental illness",
        "diagnosis", "diagnosed", "hospital", "hospitalized", "rehab", "addiction", "addicted",
        "sober", "sobriety", "hiv", "std", "stds", "sti", "insomnia", "schizophrenia", "trauma",
    ),
    "sexuality": (
        "gay", "lesbian", "bisexual", "queer", "trans", "transgender", "nonbinary", "non binary",
        "asexual", "lgbt", "lgbtq", "lgbtqia", "closeted", "coming out", "sexuality",
        "sexual orientation", "sex life",
    ),
    "religion": (
        "christian", "christians", "muslim", "muslims", "jewish", "jew", "hindu", "buddhist", "sikh",
        "atheist", "atheists", "catholic", "mormon", "evangelical", "church", "mosque", "synagogue",
        "religion", "religious", "faith", "bible", "quran", "torah", "prayer", "praying", "god",
        "ramadan", "sabbath",
    ),
    "finances": (
        "broke", "debt", "debts", "student loan", "student loans", "loan", "loans", "rent money",
        "cant afford", "cannot afford", "can't afford", "poverty", "poor", "food stamps",
        "financial aid", "paycheck", "salary", "income", "bankrupt", "bankruptcy", "money problems",
        "evicted", "eviction", "homeless", "homelessness", "unemployed", "overdraft",
    ),
    "family_trauma": (
        "divorce", "divorced", "abuse", "abused", "abusive", "neglect", "neglected", "foster care",
        "orphan", "orphaned", "estranged", "grief", "grieving", "passed away", "funeral",
        "alcoholic", "domestic violence", "custody", "deported", "deportation", "miscarriage",
        "disowned", "kicked out",
    ),
    "home_location": (
        "home address", "my address", "their address", "lives at", "lives on", "apartment", "apt",
        "dorm room", "room number", "zip code", "zipcode", "hometown", "where i live",
        "where they live",
    ),
}


def _phrase_pattern(phrases: Iterable[str]) -> re.Pattern[str]:
    alts = sorted({" ".join(words(p)) for p in phrases if words(p)}, key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(a) for a in alts) + r")(?![a-z0-9])")


_SENSITIVE = _phrase_pattern(t for terms in SENSITIVE_TERMS.values() for t in terms)

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


class OutputGuard:
    """Stateless; one instance can be shared across owners and threads."""

    def __init__(self, quote_words: int = QUOTE_WORDS):
        if quote_words < 2:
            raise ValueError("quote_words must be >= 2")
        self._n = quote_words

    # ----------------------------------------------------------------- checks
    def quotes_answer(self, text: str, against_answers: Sequence[str]) -> bool:
        grams = _ngrams(words(text), self._n)
        if not grams:
            return False
        return any(grams & _ngrams(words(a), self._n) for a in against_answers)

    @staticmethod
    def has_sensitive_term(text: str) -> bool:
        return bool(_SENSITIVE.search(" ".join(words(text))))

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
