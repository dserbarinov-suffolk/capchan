from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Union


@dataclass(frozen=True)
class FrameConfig:
    sample_fps: float = 2.0
    diff_width: int = 96
    diff_height: int = 54
    static_threshold: Union[str, float] = "auto"
    min_segment_seconds: float = 2.0
    text_overlap: float = 0.85
    min_text_tokens: int = 3
    ocr_lang: str = "eng"
    ocr_psm: int = 6

    def to_dict(self) -> dict:
        return asdict(self)
