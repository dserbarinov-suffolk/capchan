from __future__ import annotations

import re
from dataclasses import dataclass

from framechan.domain.text import containment, tokenize

from .caption import CaptionCandidate, CaptionEvent


@dataclass(frozen=True)
class EventMergeDecision:
    segment: int
    relation: str
    current_subset_of_new: float
    new_subset_of_current: float


_SPACE = re.compile(r"\s+")


def normalize_caption(text: str) -> str:
    return _SPACE.sub(" ", text).strip()


def merge_events(
    candidates: list[CaptionCandidate],
    overlap: float,
    max_gap: float,
) -> tuple[list[CaptionEvent], list[EventMergeDecision]]:
    events: list[CaptionEvent] = []
    decisions: list[EventMergeDecision] = []
    current: CaptionCandidate | None = None

    def flush() -> None:
        if current is not None:
            events.append(
                CaptionEvent(
                    index=len(events) + 1,
                    start_t=current.start_t,
                    end_t=current.end_t,
                    text=current.text,
                )
            )

    for candidate in candidates:
        normalized = normalize_caption(candidate.text)
        if not normalized:
            continue
        candidate = CaptionCandidate(
            candidate.segment, candidate.start_t, candidate.end_t, normalized
        )
        if current is None:
            decisions.append(EventMergeDecision(candidate.segment, "first", 0.0, 0.0))
            current = candidate
            continue

        cur_tokens = tokenize(current.text)
        new_tokens = tokenize(candidate.text)
        cur_in_new = containment(cur_tokens, new_tokens)
        new_in_cur = containment(new_tokens, cur_tokens)
        adjacent = candidate.start_t - current.end_t <= max_gap
        same = adjacent and (
            current.text.casefold() == candidate.text.casefold()
            or (cur_in_new >= overlap and new_in_cur >= overlap)
        )
        relation = "same" if same else "new"
        decisions.append(
            EventMergeDecision(candidate.segment, relation, round(cur_in_new, 3), round(new_in_cur, 3))
        )
        if same:
            current = CaptionCandidate(current.segment, current.start_t, candidate.end_t, current.text)
        else:
            flush()
            current = candidate

    flush()
    return events, decisions
