from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from PIL import Image

from framechan.domain.text import RecognizedText, TextBox


class FakeRecognizer:
    def __init__(self, texts: Iterable[str]) -> None:
        self._texts = deque(texts)

    def recognize(self, image: Image.Image) -> RecognizedText:
        text = self._texts.popleft() if self._texts else ""
        if not text:
            return RecognizedText(())
        return RecognizedText((TextBox(text, 1.0, (0.0, 0.0, 1.0, 0.1)),))
