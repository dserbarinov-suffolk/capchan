from __future__ import annotations

from pathlib import Path

from deckchan.domain.slide import SlideCandidate, merge_slides
from framechan.domain.segment import Segment
from framechan.domain.text import RecognizedText, SegmentText, TextBox, tokenize


def _candidate(index: int, text: str) -> SlideCandidate:
    segment = Segment(
        index=index,
        start_t=float(index * 10),
        end_t=float(index * 10 + 5),
        representative_t=float(index * 10 + 4.5),
        n_samples=10,
        passed=True,
    )
    recognized = RecognizedText((TextBox(text, 0.9, (0.0, 0.0, 1.0, 0.1)),))
    segment_text = SegmentText(segment, recognized, frozenset(tokenize(text)))
    return SlideCandidate(segment_text, Path(f"seg{index}.png"))


def test_slide_merge_keeps_builds_as_one_slide() -> None:
    slides, decisions = merge_slides(
        [
            _candidate(0, "Agenda kickoff"),
            _candidate(1, "Agenda kickoff launch"),
            _candidate(2, "Financial summary"),
        ],
        overlap=0.85,
        min_tokens=2,
        coalesce_gap=1.0,
    )

    assert [d.relation for d in decisions] == ["first", "build", "new"]
    assert len(slides) == 2
    assert slides[0].source_segments == (0, 1)
    assert slides[0].representative_frame == Path("seg1.png")
    assert slides[0].text == "Agenda kickoff launch"
