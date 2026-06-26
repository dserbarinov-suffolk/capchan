from __future__ import annotations

import re
from collections.abc import Sequence

from PIL import Image

from framechan.domain.text import RecognizedText, TextBox

_LANGUAGE_ALIASES = {
    "en": "en-US",
    "eng": "en-US",
    "english": "en-US",
    "ja": "ja-JP",
    "jpn": "ja-JP",
    "japanese": "ja-JP",
}


class VisionRecognizer:
    """Apple Vision OCR boundary.

    The adapter module is intentionally isolated as the only Apple-specific OCR
    location. It is not the default because the local test path uses Tesseract,
    but it can be selected on macOS with the optional ``ocrmac`` dependency.
    """

    def __init__(
        self,
        language_preference: str | Sequence[str] | None = None,
        recognition_level: str = "accurate",
        confidence_threshold: float = 0.0,
    ) -> None:
        self.language_preference = _normalise_language_preferences(language_preference)
        self.recognition_level = recognition_level
        self.confidence_threshold = confidence_threshold

    def recognize(self, image: Image.Image) -> RecognizedText:
        try:
            from ocrmac import ocrmac
        except ImportError as exc:
            raise RuntimeError(
                "Apple Vision OCR requires the optional dependency `ocrmac`; "
                "run with `uv run --extra vision ...` on macOS."
            ) from exc

        rows = ocrmac.OCR(
            image,
            framework="vision",
            recognition_level=self.recognition_level,
            language_preference=self.language_preference,
            confidence_threshold=self.confidence_threshold,
        ).recognize()
        lines = [
            TextBox(
                text=text.strip(),
                confidence=float(confidence),
                bbox=_vision_bbox_to_textbox_bbox(bbox),
            )
            for text, confidence, bbox in rows
            if text.strip()
        ]
        return RecognizedText(tuple(lines))


def _normalise_language_preferences(
    language_preference: str | Sequence[str] | None,
) -> list[str] | None:
    if language_preference is None:
        return None
    if isinstance(language_preference, str):
        requested = [part for part in re.split(r"[+,]", language_preference) if part]
    else:
        requested = list(language_preference)

    normalised = []
    for language in requested:
        key = language.strip()
        if not key:
            continue
        normalised.append(_LANGUAGE_ALIASES.get(key.lower(), key))
    return normalised or None


def _vision_bbox_to_textbox_bbox(bbox: Sequence[float]) -> tuple[float, float, float, float]:
    left, bottom, width, height = (float(value) for value in bbox)
    top = 1.0 - bottom - height
    right = left + width
    lower = top + height
    left = _clamp01(left)
    top = _clamp01(top)
    right = _clamp01(right)
    lower = _clamp01(lower)
    return (left, top, max(0.0, right - left), max(0.0, lower - top))


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))
