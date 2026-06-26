from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CaptionCandidate:
    segment: int
    start_t: float
    end_t: float
    text: str


@dataclass(frozen=True)
class CaptionEvent:
    index: int
    start_t: float
    end_t: float
    text: str
