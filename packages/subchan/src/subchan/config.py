from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from framechan.config import FrameConfig

RecognitionMode = Literal["banded", "full-frame"]
ImageConditioning = Literal["brightness", "subtitle-outline", "none"]
OcrEngine = Literal["auto", "tesseract", "vision"]


@dataclass(frozen=True)
class SubConfig:
    frame: FrameConfig = field(default_factory=FrameConfig)
    mode: RecognitionMode = "banded"
    ocr_engine: OcrEngine = "auto"
    band_top: float = 0.70
    band_bottom: float = 0.95
    conditioning: ImageConditioning = "brightness"
    brightness_threshold: int = 170
    min_confidence: float = 0.0
    min_box_height: float = 0.015
    max_box_height: float = 0.18
    same_text_overlap: float = 0.85
    max_merge_gap: float = 0.5
    make_vtt: bool = False
