from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Literal

from framechan.domain.text import RecognizedText, TextBox

CaptionMode = Literal["banded", "full-frame"]
TextScript = Literal["none", "japanese"]


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
    text_script: TextScript = "none",
) -> CaptionDiscriminationResult:
    decisions: list[CaptionBoxDecision] = []
    kept: list[TextBox] = []
    for raw_line in recognized.ordered_lines:
        cleaned_text, cleanup_reasons = _clean_text_for_script(raw_line.text, text_script)
        line = TextBox(cleaned_text, raw_line.confidence, raw_line.bbox)
        score, reasons = _score_line(line, mode, segment_duration, min_box_height, max_box_height)
        reasons.extend(cleanup_reasons)
        script_reject_reasons = [reason for reason in cleanup_reasons if reason == "missing_japanese"]
        quality_reasons = _text_quality_reject_reasons(line.text)
        reasons.extend(quality_reasons)
        keep = (
            not script_reject_reasons
            and not quality_reasons
            and bool(line.text.strip())
            and line.confidence >= min_confidence
            and score >= 0.35
        )
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


def _text_quality_reject_reasons(text: str) -> list[str]:
    chars = [char for char in text.strip() if not char.isspace()]
    if not chars:
        return ["blank"]

    letters = [char for char in chars if _is_letter(char)]
    digits = [char for char in chars if _is_digit(char)]
    alnum_count = len(letters) + len(digits)
    symbol_count = len(chars) - alnum_count
    reasons: list[str] = []

    if len(chars) < 2:
        reasons.append("too_short")
    if not letters:
        reasons.append("no_letters")
    if len(chars) <= 4 and len(letters) < 2:
        reasons.append("too_little_text")
    if symbol_count >= alnum_count and symbol_count > 0:
        reasons.append("symbol_heavy")
    if len(letters) >= 4 and len({char.casefold() for char in letters}) == 1:
        reasons.append("repeated_character_noise")
    return reasons


def _clean_text_for_script(text: str, text_script: TextScript) -> tuple[str, list[str]]:
    text = text.strip()
    if text_script == "none":
        return text, []

    indexes = [index for index, char in enumerate(text) if _is_japanese(char)]
    if not indexes:
        return text, ["missing_japanese"]

    start = indexes[0]
    end = indexes[-1] + 1
    while start > 0 and _is_japanese_edge_punctuation(text[start - 1]):
        start -= 1
    while end < len(text) and _is_japanese_edge_punctuation(text[end]):
        end += 1
    cleaned = text[start:end].strip()
    reasons = ["script_trimmed"] if cleaned != text else []
    return cleaned, reasons


def _is_letter(char: str) -> bool:
    return unicodedata.category(char).startswith("L")


def _is_digit(char: str) -> bool:
    return unicodedata.category(char).startswith("N")


def _is_japanese(char: str) -> bool:
    return (
        "\u3040" <= char <= "\u309f"
        or "\u30a0" <= char <= "\u30ff"
        or "\u3400" <= char <= "\u9fff"
        or "\uf900" <= char <= "\ufaff"
        or char == "々"
    )


def _is_japanese_edge_punctuation(char: str) -> bool:
    return char in "、。，．！？!?ー〜・「」『』（）()…"


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
