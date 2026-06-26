from __future__ import annotations

from typing import Protocol

from PIL import Image

from framechan.domain.text import RecognizedText


class TextRecognizer(Protocol):
    def recognize(self, image: Image.Image) -> RecognizedText:
        """Return recognized lines, each with text, confidence, and a bounding box."""
