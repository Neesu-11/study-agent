"""Pick short excerpts from notes and textbooks for the current topic."""

from __future__ import annotations

import re
from dataclasses import dataclass

from study_tutor.config import MATERIAL_PROMPT_CHARS

_STOP = {
    "about",
    "after",
    "also",
    "analysis",
    "and",
    "from",
    "into",
    "that",
    "their",
    "this",
    "with",
    "your",
}


@dataclass
class Material:
    title: str
    kind: str
    content: str


def select_excerpts(materials: list[Material], *hints: str, limit: int = MATERIAL_PROMPT_CHARS) -> str:
    keywords = _keywords(" ".join(hints))
    if not materials:
        return ""
    chunks: list[tuple[int, str, str]] = []
    for material in materials:
        for paragraph in re.split(r"\n\s*\n", material.content):
            text = paragraph.strip()
            if len(text) < 40:
                continue
            score = _score(text, keywords) + (3 if _score(material.title, keywords) else 0)
            chunks.append((score, material.title, text))
    chunks.sort(key=lambda item: item[0], reverse=True)
    chosen = [item for item in chunks if item[0] > 0]
    if not chosen:
        newest = materials[-1]
        snippet = newest.content.strip()[:2000]
        if not snippet:
            return ""
        return f"Source: {newest.title}\n{snippet}"
    parts: list[str] = []
    used = 0
    seen: set[str] = set()
    for _score_value, title, text in chosen:
        clipped = text[:1500]
        marker = clipped[:120]
        if marker in seen:
            continue
        seen.add(marker)
        block = f"Source: {title}\n{clipped}"
        if used + len(block) > limit:
            break
        parts.append(block)
        used += len(block)
        if len(parts) >= 4:
            break
    return "\n\n".join(parts)


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [word for word in words if len(word) > 3 and word not in _STOP]


def _score(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    return sum(lowered.count(word) for word in keywords)
