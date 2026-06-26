from __future__ import annotations

from PIL import Image

from framechan.domain.text import RecognizedText


class VisionRecognizer:
    """Apple Vision OCR boundary.

    The adapter module is intentionally isolated as the only Apple-specific OCR
    location. It is not the default in this repo because the local test path uses
    Tesseract, but a production Vision implementation belongs here.
    """

    def __init__(self) -> None:
        raise RuntimeError("VisionRecognizer is not implemented; use TesseractRecognizer")

    def recognize(self, image: Image.Image) -> RecognizedText:
        raise RuntimeError("VisionRecognizer is not implemented")
