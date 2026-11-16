"""Text clean-up used by both parts: HTML to plain text, sentence splitting, chunking."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup


def html_to_text(html: bytes | str) -> str:
    """Strip tags, scripts and hidden XBRL headers; collapse whitespace."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    for tag in soup.find_all(["ix:header"]):          # inline-XBRL metadata block
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


_ITEM1 = re.compile(r"item\s*1\s*[\.\:\-–—]?\s*business\b", re.I)
_ITEM1A = re.compile(r"item\s*1a\s*[\.\:\-–—]?\s*risk\s*factors", re.I)


def extract_business_section(text: str, min_chars: int = 1500) -> str | None:
    """Return 10-K 'Item 1. Business' text, or None if it can't be found.

    The table of contents also says 'Item 1. Business', so we try every match and
    keep the longest stretch that runs up to the next 'Item 1A. Risk Factors'.
    """
    best = ""
    for m in _ITEM1.finditer(text):
        end = _ITEM1A.search(text, m.end())
        if end:
            span = text[m.end():end.start()]
            if len(span) > len(best):
                best = span
    best = best.strip()
    return best if len(best) >= min_chars else None


_SENT_SPLIT = re.compile(r"(?<=[\.\;\!\?])\s+(?=[A-Z\(\"“0-9])|\n+")


def split_sentences(text: str) -> list[str]:
    """Simple rule-based sentence splitter (good enough for legal/terms text)."""
    parts = _SENT_SPLIT.split(text)
    return [re.sub(r"\s+", " ", p).strip() for p in parts if len(p.strip()) > 20]


def chunk_words(text: str, size: int = 200, max_chunks: int = 400) -> list[str]:
    """Cut text into ~size-word chunks; if there are too many, take an even sample."""
    words = text.split()
    chunks = [" ".join(words[i:i + size]) for i in range(0, len(words), size)]
    if len(chunks) > max_chunks:
        step = len(chunks) / max_chunks
        chunks = [chunks[int(i * step)] for i in range(max_chunks)]
    return [c for c in chunks if len(c.split()) >= 30] or chunks[:1]
