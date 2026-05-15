from __future__ import annotations

import logging
import re
import unicodedata
from functools import lru_cache

LOG = logging.getLogger(__name__)

_NOISE_PATTERNS = [
    r"\bfeat\.?\s+[^([]+",
    r"\bft\.?\s+[^([]+",
    r"\bfaturing\s+[^([]+",
    r"\([^)]*remaster[^)]*\)",
    r"\[[^\]]*remaster[^\]]*\]",
    r"\([^)]*live[^)]*\)",
    r"\([^)]*deluxe[^)]*\)",
    r"\([^)]*radio edit[^)]*\)",
    r"\bradio edit\b",
]


def strip_accents(s: str) -> str:
    nk = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nk if not unicodedata.combining(c))


def remove_punctuation(s: str) -> str:
    return re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)


def collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def strip_noise_terms(text: str, enabled: bool = True) -> str:
    if not enabled:
        return text
    t = text
    for pat in _NOISE_PATTERNS:
        t = re.sub(pat, " ", t, flags=re.IGNORECASE)
    return collapse_ws(t)


def normalize_for_matching(text: str, *, strip_noise: bool = True) -> str:
    """Lowercase, strip accents, remove punctuation, collapse whitespace, optional noise stripping."""
    if not text:
        return ""
    t = strip_accents(text).lower()
    t = remove_punctuation(t)
    t = collapse_ws(t)
    if strip_noise:
        t = strip_noise_terms(t, enabled=True)
    return collapse_ws(t)


def build_queries(artist: str, title: str, *, strip_noise: bool = True) -> tuple[str, str, str]:
    """artist+title, title+artist, title only — human-facing search strings."""
    a = collapse_ws(artist.strip())
    ti = collapse_ws(title.strip())
    ti_clean = strip_noise_terms(ti, enabled=strip_noise) if strip_noise else ti
    at = collapse_ws(f"{a} {ti_clean}".strip())
    ta = collapse_ws(f"{ti_clean} {a}".strip()) if a else ti_clean
    to = ti_clean or ti
    return at, ta, to


@lru_cache(maxsize=1)
def non_music_kind_substrings() -> tuple[str, ...]:
    return (
        "podcast",
        "audiobook",
        "pdf",
        "book",
        "music video",
        "mpeg-4 movie",
        "tv",
        "itunes u",
        "ringtone",
        "voice memo",
        "midi",
    )


def is_music_kind(kind: str | None) -> bool:
    if not kind:
        return True
    k = kind.lower()
    return not any(sub in k for sub in non_music_kind_substrings())
