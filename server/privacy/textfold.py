"""Obfuscation-resistant text folding shared by OutputGuard and the M1 code pre-screen.

``fold(text)`` returns lowercase ASCII-ish tokens joined by single spaces, in this order:

1. ``normalize``: NFKC (fullwidth -> ASCII), invisible format characters
   (zero-width space/joiner, soft hyphen, ...) removed, lowercase, curly
   apostrophes unified. Zero-width characters are *removed* rather than turned
   into spaces so "w<ZWSP>o<ZWSP>r<ZWSP>d" folds back to "word" (a space would
   leave two-letter words such as "i n" split).
2. Accents stripped (NFD, combining marks dropped): "thérapy" -> "therapy".
3. Confusables: Cyrillic/Greek/IPA look-alikes folded to the Latin letter they
   imitate: "d<Cyrillic e>pression" -> "depression". The list is the visual
   look-alike set from the safety eval, not the full Unicode confusables.txt.
4. Leet, but only inside tokens that mix letters with digits or ``@``/``$``
   ("k1ll", "d3pression", "m@ss"), so plain numbers ("4 of 7", "3:30") are
   untouched.
5. ``.``, ``_`` and ``-`` become spaces; apostrophes are dropped inside words
   ("don't" -> "dont"); every other symbol becomes a space.
6. Runs of three or more single letters are joined: "d e p r e s s i o n" ->
   "depression", "k i l l" -> "kill".

Deterministic and offline. Nothing here logs or keeps the text.
"""

from __future__ import annotations

import re
import unicodedata

_APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "`": "'", "\u00b4": "'"})

# Lowercase look-alike -> Latin letter (input is already lowercased by normalize).
CONFUSABLES: dict[str, str] = {
    # Cyrillic
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c", "\u0443": "y",
    "\u0445": "x", "\u0456": "i", "\u0458": "j", "\u0455": "s", "\u04bb": "h", "\u0501": "d",
    "\u051d": "w", "\u04cf": "l",
    # Greek
    "\u03bf": "o", "\u03b1": "a", "\u03b5": "e", "\u03b9": "i", "\u03ba": "k", "\u03bd": "v",
    "\u03c1": "p", "\u03c4": "t", "\u03c5": "u", "\u03c7": "x",
    # IPA / Latin extensions
    "\u0261": "g", "\u0251": "a", "\u0131": "i",
}
_CONFUSABLE_TABLE = str.maketrans(CONFUSABLES)
_LEET_TABLE = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})
_LEET_RUN = re.compile(r"[a-z0-9@$]+")
_HAS_LETTER = re.compile(r"[a-z]")
_HAS_LEET = re.compile(r"[0-9@$]")
_SEPARATORS = re.compile(r"[._\-]+")
_INNER_APOSTROPHE = re.compile(r"(?<=[a-z0-9])'(?=[a-z0-9])")
_NON_WORD = re.compile(r"[^a-z0-9 ]+")
_SINGLE_LETTER_RUN = re.compile(r"(?<![a-z0-9])(?:[a-z] ){2,}[a-z](?![a-z0-9])")


def normalize(text: str) -> str:
    """NFKC, drop invisible format chars (zero-width etc.), lowercase, unify apostrophes."""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) not in {"Cf", "Cc"} or ch in "\n\t ")
    return text.translate(_APOSTROPHES).lower()


def _strip_accents(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")


def _unleet(match: re.Match[str]) -> str:
    run = match.group(0)
    if _HAS_LETTER.search(run) and _HAS_LEET.search(run):
        return run.translate(_LEET_TABLE)
    return run


def _join_single_letters(match: re.Match[str]) -> str:
    return match.group(0).replace(" ", "")


def fold(text: str) -> str:
    """Folded, space-separated tokens (see module docstring for the order)."""
    t = _strip_accents(normalize(text)).translate(_CONFUSABLE_TABLE)
    t = _LEET_RUN.sub(_unleet, t)
    t = _SEPARATORS.sub(" ", t)
    t = _INNER_APOSTROPHE.sub("", t)
    t = " ".join(_NON_WORD.sub(" ", t).split())
    return _SINGLE_LETTER_RUN.sub(_join_single_letters, t)


def folded_words(text: str) -> list[str]:
    return fold(text).split()


def folded_chunks(text: str) -> list[str]:
    """Each whitespace-separated chunk of the original text, folded with its
    internal separators removed: "#depression_squad" -> "depressionsquad",
    "the.rapist" -> "therapist". Used for the compact (no-space) term check;
    chunks never span two words the writer separated with a space."""
    return [c for c in (fold(chunk).replace(" ", "") for chunk in normalize(text).split()) if c]


def stem(token: str) -> str:
    """Light plural stem so "escapes"/"escape" and "pizzas"/"pizza" compare equal."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith(("ches", "shes", "sses", "xes", "zes")):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token
