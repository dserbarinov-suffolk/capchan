from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .segment import Segment

TextRelation = Literal["equal", "subset", "different"]


@dataclass(frozen=True)
class TextBox:
    text: str
    confidence: float
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class RecognizedText:
    lines: tuple[TextBox, ...]

    @property
    def ordered_lines(self) -> tuple[TextBox, ...]:
        return tuple(sorted(self.lines, key=lambda b: (round(b.bbox[1], 3), b.bbox[0])))

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.ordered_lines if line.text.strip())


@dataclass(frozen=True)
class SegmentText:
    segment: Segment
    recognized: RecognizedText
    tokens: frozenset[str]


_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str, min_len: int = 2) -> set[str]:
    return {tok for tok in _TOKEN.findall(text.lower()) if len(tok) >= min_len}


def containment(a: set[str] | frozenset[str], b: set[str] | frozenset[str]) -> float:
    return len(a & b) / len(a) if a else 0.0


def identity_relation(
    current: set[str] | frozenset[str],
    new: set[str] | frozenset[str],
    overlap: float,
) -> TextRelation:
    current_in_new = containment(current, new)
    new_in_current = containment(new, current)
    if current_in_new >= overlap and new_in_current >= overlap:
        return "equal"
    if current_in_new >= overlap:
        return "subset"
    return "different"
