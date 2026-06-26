"""Stage 3 — OCR, the thing that actually gives a slide its identity.

The backend is a one-method protocol so the engine is swappable. The default is
Tesseract because it is portable. On macOS you can drop in Apple's Vision OCR
(fast, on-device) by implementing the same `text()` method — see the README.

Tokenisation turns a frame's text into a *set* of normalised tokens. Sets, not
strings, because the identity logic downstream is about set relations: equality
for "same slide", and the subset relation for "progressive build".
"""

from __future__ import annotations

import re
from typing import Protocol

import pytesseract
from PIL import Image


class OCRBackend(Protocol):
    def text(self, image: Image.Image) -> str: ...


class TesseractBackend:
    def __init__(self, lang: str = "eng", psm: int = 6) -> None:
        self.lang = lang
        self.config = f"--psm {psm}"

    def text(self, image: Image.Image) -> str:
        return pytesseract.image_to_string(image, lang=self.lang, config=self.config)


_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str, min_len: int = 2) -> set[str]:
    """Lowercase, keep alphanumeric runs of length >= min_len, return a set.

    The length filter drops stray single characters, which is exactly where most
    OCR noise lives.
    """
    return {tok for tok in _TOKEN.findall(text.lower()) if len(tok) >= min_len}
