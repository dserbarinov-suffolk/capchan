from __future__ import annotations

from subchan.adapters.srt_writer import SrtSubtitleWriter
from subchan.adapters.vtt_writer import VttSubtitleWriter
from subchan.domain.caption import CaptionEvent


def test_srt_writer_formats_timecodes(tmp_path) -> None:
    path = tmp_path / "captions.srt"
    SrtSubtitleWriter().write([CaptionEvent(1, 1.2, 3.456, "hello")], path)

    assert path.read_text() == "1\n00:00:01,200 --> 00:00:03,456\nhello\n\n"


def test_vtt_writer_formats_timecodes(tmp_path) -> None:
    path = tmp_path / "captions.vtt"
    VttSubtitleWriter().write([CaptionEvent(1, 1.2, 3.456, "hello")], path)

    assert path.read_text() == "WEBVTT\n\n00:00:01.200 --> 00:00:03.456\nhello\n\n"
