from __future__ import annotations

from dataclasses import dataclass, field

from framechan.config import FrameConfig


@dataclass(frozen=True)
class DeckConfig:
    frame: FrameConfig = field(default_factory=FrameConfig)
    make_pptx: bool = False
