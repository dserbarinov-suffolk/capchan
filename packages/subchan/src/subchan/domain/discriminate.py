from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from framechan.domain.text import RecognizedText, TextBox

CaptionMode = Literal["banded", "full-frame"]


@dataclass(frozen=True)
class CaptionBoxDecision:
    text: str
    confidence: float
    bbox: tuple[float, float, float, float]
    score: float
    kept: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CaptionDiscriminationResult:
    text: str
    decisions: tuple[CaptionBoxDecision, ...]


def discriminate_caption(
    recognized: RecognizedText,
    mode: CaptionMode,
    segment_duration: float,
    min_confidence: float,
    min_box_height: float,
    max_box_height: float,
) -> CaptionDiscriminationResult:
    decisions: list[CaptionBoxDecision] = []
    kept: list[TextBox] = []
    for line in recognized.ordered_lines:
        score, reasons = _score_line(line, mode, segment_duration, min_box_height, max_box_height)
        keep = bool(line.text.strip()) and line.confidence >= min_confidence and score >= 0.35
        decisions.append(
            CaptionBoxDecision(
                text=line.text,
                confidence=line.confidence,
                bbox=line.bbox,
                score=round(score, 3),
                kept=keep,
                reasons=tuple(reasons),
            )
        )
        if keep:
            kept.append(line)
    text = "\n".join(line.text.strip() for line in kept if line.text.strip())
    return CaptionDiscriminationResult(text=text, decisions=tuple(decisions))


def _score_line(
    line: TextBox,
    mode: CaptionMode,
    segment_duration: float,
    min_box_height: float,
    max_box_height: float,
) -> tuple[float, list[str]]:
    if mode == "banded":
        return 1.0, ["banded"]

    _, y, _, h = line.bbox
    score = 0.0
    reasons: list[str] = []
    if 0.7 <= segment_duration <= 12.0:
        score += 0.35
        reasons.append("persistence")
    elif segment_duration <= 20.0:
        score += 0.2
        reasons.append("weak_persistence")
    if min_box_height <= h <= max_box_height:
        score += 0.25
        reasons.append("size")
    if line.confidence >= 0.4:
        score += 0.2
        reasons.append("confidence")
    if y >= 0.45:
        score += 0.15
        reasons.append("position")
    return min(score, 1.0), reasons
