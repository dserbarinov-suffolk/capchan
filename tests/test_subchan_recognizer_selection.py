from __future__ import annotations

from framechan.adapters.tesseract_recognizer import TesseractRecognizer
from framechan.adapters.vision_recognizer import VisionRecognizer
from subchan.application import extract_subtitles
from subchan.application.extract_subtitles import _build_recognizer, _resolve_text_script
from subchan.config import SubConfig
from framechan.config import FrameConfig


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


def test_auto_text_script_requires_japanese_for_japanese_ocr() -> None:
    config = SubConfig(frame=FrameConfig(ocr_lang="jpn"))

    assert _resolve_text_script(config) == "japanese"


def test_auto_text_script_does_not_filter_english_ocr() -> None:
    config = SubConfig(frame=FrameConfig(ocr_lang="eng"))

    assert _resolve_text_script(config) == "none"
