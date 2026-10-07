"""Text normalisation for deterministic phrase matching.

``normalise_for_matching`` produces a comparison key only. Callers must keep
passing the original text downstream (providers, Laya, instrument resolution)
so user content and financial identifiers are never rewritten.
"""

from __future__ import annotations

import re
import unicodedata

_PUNCTUATION = str.maketrans(
    {
        # Apostrophe look-alikes (smart quotes from phones/voice transcripts).
        "‘": "'",
        "’": "'",
        "‛": "'",
        "ʼ": "'",
        "′": "'",
        "´": "'",
        "`": "'",
        # Double quotes.
        "“": '"',
        "”": '"',
        "‟": '"',
        "″": '"',
        # Hyphens and dashes.
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "−": "-",
        # Arabic code points commonly typed for their Persian equivalents.
        "ي": "ی",  # ARABIC YEH -> FARSI YEH
        "ى": "ی",  # ARABIC ALEF MAKSURA -> FARSI YEH
        "ك": "ک",  # ARABIC KAF -> KEHEH
    }
)
_WHITESPACE = re.compile(r"\s+")


def normalise_for_matching(text: str) -> str:
    """Return a casefolded, punctuation-canonical key for phrase matching.

    NFKC folds compatibility forms (full-width letters, Arabic presentation
    forms); typographic apostrophes, quotes and dashes map to ASCII; Arabic
    yeh/kaf map to their Persian forms; whitespace collapses. Letters, digits,
    ``/``, ``&`` and the Persian zero-width non-joiner are preserved, so
    identifiers such as ``EUR/USD``, ``S&P 500`` or ``بیت‌کوین`` still match.
    """
    value = unicodedata.normalize("NFKC", text).translate(_PUNCTUATION)
    return _WHITESPACE.sub(" ", value.casefold()).strip()
