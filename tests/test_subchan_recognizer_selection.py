from __future__ import annotations

from framechan.adapters.tesseract_recognizer import TesseractRecognizer
from framechan.adapters.vision_recognizer import VisionRecognizer
from subchan.application import extract_subtitles
from subchan.application.extract_subtitles import _build_recognizer
from subchan.config import SubConfig


def test_auto_uses_vision_on_macos_when_ocrmac_is_available(monkeypatch) -> None:
    monkeypatch.setattr(extract_subtitles.sys, "platform", "darwin")
    monkeypatch.setattr(
        extract_subtitles.importlib.util,
        "find_spec",
        lambda name: object() if name == "ocrmac" else None,
    )

    recognizer = _build_recognizer(SubConfig(ocr_engine="auto"))

    assert isinstance(recognizer, VisionRecognizer)


def test_auto_falls_back_to_tesseract_when_vision_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(extract_subtitles.sys, "platform", "linux")
    monkeypatch.setattr(extract_subtitles.importlib.util, "find_spec", lambda name: None)

    recognizer = _build_recognizer(SubConfig(ocr_engine="auto"))

    assert isinstance(recognizer, TesseractRecognizer)
