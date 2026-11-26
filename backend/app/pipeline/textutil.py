"""Small text helpers shared by the pipeline and the offline provider."""

import re
import unicodedata

from rapidfuzz import fuzz

_WS = re.compile(r"\s+")
_SENT_SPLIT = re.compile(r"(?<=[.!?;])\s+(?=[A-Z(\"'“])")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9+\-]*|\d+(?:\.\d+)?%?")
PAGE_MARKER = re.compile(r"\[\[page (\d+)\]\]")

STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "by",
        "at",
        "from",
        "as",
        "is",
        "are",
        "be",
        "been",
        "being",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "into",
        "within",
        "than",
        "then",
        "there",
        "their",
        "them",
        "they",
        "which",
        "who",
        "whom",
        "whose",
        "will",
        "shall",
        "must",
        "should",
        "may",
        "can",
        "could",
        "would",
        "also",
        "all",
        "any",
        "each",
        "every",
        "such",
        "other",
        "including",
        "include",
        "includes",
        "per",
        "via",
        "under",
        "over",
        "upto",
        "up",
        "not",
        "no",
        "nor",
        "if",
        "so",
        "do",
        "does",
        "done",
        "provide",
        "provides",
        "provided",
        "providing",
        "ensure",
        "ensures",
        "support",
        "bidder",
        "bidders",
        "vendor",
        "vendors",
        "contractor",
        "agency",
        "solution",
        "system",
        "systems",
        "proposed",
        "required",
        "requirement",
        "requirements",
        "following",
        "said",
        "same",
        "using",
        "use",
        "used",
        "where",
        "when",
        "while",
        "has",
        "have",
        "had",
        "our",
        "we",
        "us",
        "you",
        "your",
        "least",
        "minimum",
        "maximum",
        "made",
        "make",
        "makes",
        "able",
        "shall",
    ]
)


def normalize(text: str) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFKC", text)).strip()


def split_sentences(text: str) -> list[str]:
    text = normalize(text)
    if not text:
        return []
    return [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]


def words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def key_terms(text: str) -> set[str]:
    return {w for w in words(text) if w not in STOPWORDS and (len(w) > 2 or w[0].isdigit())}


def quote_found(quote: str, haystack: str, threshold: float = 90.0) -> bool:
    """True when `quote` appears (fuzzily) as a contiguous span of `haystack`."""
    q = normalize(quote).lower()
    h = normalize(haystack).lower()
    if len(q) < 12:
        return False
    if q in h:
        return True
    return fuzz.partial_ratio(q, h) >= threshold


def similarity(a: str, b: str) -> float:
    """0-1 token-set similarity used for de-duplication and matching."""
    return fuzz.token_set_ratio(normalize(a).lower(), normalize(b).lower()) / 100.0


def snake_case(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:60] or "field"
