from __future__ import annotations

from framechan.domain.text import RecognizedText, TextBox
from subchan.domain.discriminate import discriminate_caption
from subchan.domain.caption import CaptionCandidate
from subchan.domain.events import merge_events


def test_event_merge_combines_adjacent_same_caption_text() -> None:
    events, decisions = merge_events(
        [
            CaptionCandidate(0, 0.0, 1.0, "hello world"),
            CaptionCandidate(1, 1.0, 2.0, "Hello, world!"),
            CaptionCandidate(2, 4.0, 5.0, "next line"),
        ],
        overlap=0.85,
        max_gap=0.25,
    )

    assert [d.relation for d in decisions] == ["first", "same", "new"]
    assert len(events) == 2
    assert events[0].start_t == 0.0
    assert events[0].end_t == 2.0
    assert events[0].text == "hello world"
    assert events[1].index == 2


def test_caption_discrimination_rejects_short_symbol_heavy_ocr_noise() -> None:
    recognized = RecognizedText(
        lines=(
            TextBox("1,/", 0.5, (0.6, 0.0, 0.04, 0.08)),
            TextBox("♪ ｛", 0.5, (0.6, 0.0, 0.04, 0.08)),
            TextBox("こんにちは！", 0.5, (0.2, 0.2, 0.6, 0.2)),
        )
    )

    result = discriminate_caption(
        recognized,
        mode="banded",
        segment_duration=2.0,
        min_confidence=0.0,
        min_box_height=0.015,
        max_box_height=0.18,
    )

    assert result.text == "こんにちは！"
    assert result.decisions[0].kept is False
    assert "no_letters" in result.decisions[0].reasons
    assert result.decisions[1].kept is False
    assert "symbol_heavy" in result.decisions[1].reasons
    assert result.decisions[2].kept is True


def test_caption_discrimination_rejects_repeated_character_noise() -> None:
    result = discriminate_caption(
        RecognizedText((TextBox("IIIII", 0.5, (0.2, 0.2, 0.2, 0.1)),)),
        mode="banded",
        segment_duration=2.0,
        min_confidence=0.0,
        min_box_height=0.015,
        max_box_height=0.18,
    )

    assert result.text == ""
    assert "repeated_character_noise" in result.decisions[0].reasons


def test_caption_discrimination_requires_japanese_when_requested() -> None:
    result = discriminate_caption(
        RecognizedText(
            (
                TextBox("9TO", 0.5, (0.2, 0.2, 0.2, 0.1)),
                TextBox("FUMOTO TPPARAI こんぐらいかな", 0.5, (0.2, 0.3, 0.5, 0.1)),
                TextBox("カロリーなんて気にし BRANDOORES", 0.5, (0.2, 0.4, 0.5, 0.1)),
            )
        ),
        mode="banded",
        segment_duration=2.0,
        min_confidence=0.0,
        min_box_height=0.015,
        max_box_height=0.18,
        text_script="japanese",
    )

    assert result.text == "こんぐらいかな\nカロリーなんて気にし"
    assert result.decisions[0].kept is False
    assert "missing_japanese" in result.decisions[0].reasons
    assert "script_trimmed" in result.decisions[1].reasons
    assert "script_trimmed" in result.decisions[2].reasons
