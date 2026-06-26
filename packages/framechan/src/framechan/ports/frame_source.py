from __future__ import annotations

from typing import Any, Iterator, Protocol
from PIL import Image


class FrameSource(Protocol):
    def samples(self, fps: float, width: int, height: int) -> Iterator[tuple[float, Any]]:
        """Yield sampled downscaled grayscale frames across the whole video."""

    def frame_at(self, t: float) -> Image.Image:
        """Return one full-resolution frame at time t."""
