from __future__ import annotations

import numpy as np

from framechan.domain.difference import difference_series_from_samples
from framechan.domain.gate import find_segments
from framechan.domain.text import RecognizedText, TextBox, identity_relation, tokenize


def test_difference_series_and_segments_use_last_held_frame() -> None:
    samples = [
        (0.0, np.zeros((2, 2), dtype=np.uint8)),
        (1.0, np.zeros((2, 2), dtype=np.uint8)),
        (2.0, np.full((2, 2), 255, dtype=np.uint8)),
        (3.0, np.full((2, 2), 255, dtype=np.uint8)),
        (4.0, np.full((2, 2), 128, dtype=np.uint8)),
    ]

    series = difference_series_from_samples(samples, fps=1.0)
    assert tuple(round(v, 3) for v in series.diffs) == (0.0, 0.0, 1.0, 0.0, 0.498)

    segments = find_segments(series, threshold=0.25, min_seconds=0.5)
    assert [(s.start_t, s.end_t, s.passed) for s in segments] == [
        (0.0, 1.0, True),
        (2.0, 3.0, True),
        (4.0, 4.0, False),
    ]
    assert segments[0].representative_t == 0.5
    assert segments[1].representative_t == 2.5


def test_text_identity_uses_token_containment() -> None:
    current = tokenize("Agenda kickoff architecture")
    same = tokenize("Agenda kickoff architecture")
    build = tokenize("Agenda kickoff architecture launch")
    different = tokenize("Financial summary")

    assert identity_relation(current, same, overlap=0.85) == "equal"
    assert identity_relation(current, build, overlap=0.85) == "subset"
    assert identity_relation(current, different, overlap=0.85) == "different"


def test_recognized_text_orders_lines_by_box() -> None:
    recognized = RecognizedText(
        lines=(
            TextBox("second", 0.9, (0.1, 0.5, 0.2, 0.1)),
            TextBox("first", 0.9, (0.1, 0.1, 0.2, 0.1)),
        )
    )

    assert recognized.text == "first\nsecond"
