from __future__ import annotations

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
