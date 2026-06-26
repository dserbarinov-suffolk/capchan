from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from framechan.domain.text import SegmentText, containment


@dataclass(frozen=True)
class Slide:
    index: int
    source_segments: tuple[int, ...]
    occurrences: tuple[tuple[float, float], ...]
    representative_frame: Path
    text: str
    tokens: frozenset[str]


@dataclass(frozen=True)
class SlideCandidate:
    segment_text: SegmentText
    representative_frame: Path


@dataclass(frozen=True)
class SlideMergeDecision:
    segment: int
    relation: str
    current_subset_of_new: float
    new_subset_of_current: float


def _coalesce(
    intervals: list[tuple[float, float]], max_gap: float
) -> tuple[tuple[float, float], ...]:
    out: list[tuple[float, float]] = []
    for start, end in sorted(intervals):
        if out and start - out[-1][1] <= max_gap:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return tuple(out)


def _make_slide(index: int, members: list[SlideCandidate], coalesce_gap: float) -> Slide:
    rep = max(
        members,
        key=lambda item: (
            len(item.segment_text.tokens),
            -item.segment_text.segment.index,
        ),
    )
    tokens = frozenset().union(*(item.segment_text.tokens for item in members))
    text = rep.segment_text.recognized.text.replace("\n", " ")
    return Slide(
        index=index,
        source_segments=tuple(item.segment_text.segment.index for item in members),
        occurrences=_coalesce(
            [
                (item.segment_text.segment.start_t, item.segment_text.segment.end_t)
                for item in members
            ],
            coalesce_gap,
        ),
        representative_frame=rep.representative_frame,
        text=" ".join(text.split()),
        tokens=tokens,
    )


def merge_slides(
    candidates: list[SlideCandidate],
    overlap: float,
    min_tokens: int,
    coalesce_gap: float,
) -> tuple[list[Slide], list[SlideMergeDecision]]:
    slides: list[Slide] = []
    decisions: list[SlideMergeDecision] = []
    members: list[SlideCandidate] = []

    def flush() -> None:
        if members:
            slides.append(_make_slide(len(slides) + 1, members, coalesce_gap))

    for candidate in candidates:
        toks = candidate.segment_text.tokens
        segment_index = candidate.segment_text.segment.index
        if not members:
            decisions.append(SlideMergeDecision(segment_index, "first", 0.0, 0.0))
            members = [candidate]
            continue

        current = frozenset().union(*(item.segment_text.tokens for item in members))
        cur_in_new = containment(current, toks)
        new_in_cur = containment(toks, current)

        if len(toks) < min_tokens or len(current) < min_tokens:
            relation = "low_text"
        elif cur_in_new >= overlap and new_in_cur >= overlap:
            relation = "equal"
        elif cur_in_new >= overlap:
            relation = "build"
        else:
            relation = "new"

        decisions.append(
            SlideMergeDecision(segment_index, relation, round(cur_in_new, 3), round(new_in_cur, 3))
        )
        if relation in ("equal", "build"):
            members.append(candidate)
        else:
            flush()
            members = [candidate]

    flush()
    return slides, decisions
