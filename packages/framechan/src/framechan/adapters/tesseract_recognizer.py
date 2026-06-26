from __future__ import annotations

from collections import defaultdict

import pytesseract
from PIL import Image
from pytesseract import Output

from framechan.domain.text import RecognizedText, TextBox


class TesseractRecognizer:
    def __init__(self, lang: str = "eng", psm: int = 6) -> None:
        self.lang = lang
        self.config = f"--psm {psm}"

    def recognize(self, image: Image.Image) -> RecognizedText:
        data = pytesseract.image_to_data(
            image,
            lang=self.lang,
            config=self.config,
            output_type=Output.DICT,
        )
        width, height = image.size
        grouped: dict[tuple[int, int, int], list[int]] = defaultdict(list)
        for i, text in enumerate(data.get("text", [])):
            if text and text.strip():
                key = (
                    int(data["block_num"][i]),
                    int(data["par_num"][i]),
                    int(data["line_num"][i]),
                )
                grouped[key].append(i)

        lines: list[TextBox] = []
        for indexes in grouped.values():
            words = [data["text"][i].strip() for i in indexes if data["text"][i].strip()]
            if not words:
                continue
            left = min(int(data["left"][i]) for i in indexes)
            top = min(int(data["top"][i]) for i in indexes)
            right = max(int(data["left"][i]) + int(data["width"][i]) for i in indexes)
            bottom = max(int(data["top"][i]) + int(data["height"][i]) for i in indexes)
            confidences = [float(data["conf"][i]) for i in indexes if float(data["conf"][i]) >= 0]
            confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0
            lines.append(
                TextBox(
                    text=" ".join(words),
                    confidence=confidence,
                    bbox=(
                        left / width,
                        top / height,
                        max(0.0, (right - left) / width),
                        max(0.0, (bottom - top) / height),
                    ),
                )
            )
        return RecognizedText(tuple(lines))
