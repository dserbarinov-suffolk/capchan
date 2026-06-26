from __future__ import annotations

import pytest

from framechan.adapters.vision_recognizer import (
    _normalise_language_preferences,
    _vision_bbox_to_textbox_bbox,
)


def test_vision_language_preferences_accept_tesseract_style_names() -> None:
    assert _normalise_language_preferences("jpn+eng") == ["ja-JP", "en-US"]
    assert _normalise_language_preferences(["ja-JP", "eng"]) == ["ja-JP", "en-US"]
    assert _normalise_language_preferences("") is None


def test_vision_bbox_converts_from_bottom_left_to_top_left() -> None:
    assert _vision_bbox_to_textbox_bbox((0.1, 0.2, 0.3, 0.4)) == pytest.approx(
        (0.1, 0.4, 0.3, 0.4)
    )


def test_vision_bbox_clamps_to_image_bounds() -> None:
    assert _vision_bbox_to_textbox_bbox((-0.1, -0.2, 1.4, 1.3)) == (0.0, 0.0, 1.0, 1.0)
