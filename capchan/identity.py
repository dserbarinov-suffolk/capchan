"""Stage 4 — text identity: collapse candidate segments into slides.

This is the heart of it. Each candidate segment carries a token set. Walking the
candidates in time order, we compare each only to its immediate predecessor in
the candidate sequence — gaps of non-slide content are skipped, never bridged by
guesswork — and decide:

  equal text            -> the same slide (a held shot, or an immediate cut-away
                           and return); merge.
  current is subset of new -> a progressive build (a bullet appeared); merge and
                           keep the maximal, last frame, which contains all the
                           earlier content, so nothing is lost.
  either side low-text  -> can't trust a text comparison; keep both (capture).
  otherwise             -> a genuinely new slide.

Comparing only adjacent candidates keeps segmentation airtight: two distinct
slides that happen to share text can never wrongly merge unless they are
candidate-adjacent. Recognising a return to an *earlier* slide after other slides
have intervened (global dedup) is deliberately out of scope for v1 — it would
just produce a duplicate, which the one-directional error budget tolerates.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


def containment(a: set, b: set) -> float:
    """Fraction of a's tokens that also appear in b. ~1.0 means a is a subset of b."""
    return len(a & b) / len(a) if a else 0.0


@dataclass
class Slide:
    index: int
    seg_ids: list[int]
    occurrences: list[tuple[float, float]]
    rep_frame: Path
    text: str
    tokens: set[str]


@dataclass
class MergeDecision:
    seg_id: int
    relation: str  # "first" | "equal" | "build" | "low_text" | "new"
    current_in_new: float  # containment(current, new): is current a subset of new?
    new_in_current: float  # containment(new, current): is new a subset of current?


def _coalesce(intervals: list[tuple[float, float]], max_gap: float) -> list[tuple[float, float]]:
    """Join intervals that are essentially touching (presentation only).

    Build steps are separated by a single transition sample; merging their
    intervals gives one clean on-screen span for the slide. This does not affect
    any merge decision — it only tidies the reported timeline.
    """
    out: list[tuple[float, float]] = []
    for s, e in sorted(intervals):
        if out and s - out[-1][1] <= max_gap:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def merge_segments(
    records: list[dict[str, Any]],
    overlap: float,
    min_tokens: int,
    coalesce_gap: float,
) -> tuple[list[Slide], list[MergeDecision]]:
    """`records` are the captured segments in time order, each a dict with keys
    id, block (Segment), frame (Path), text (str), tokens (set)."""
    slides: list[Slide] = []
    decisions: list[MergeDecision] = []
    members: list[dict] = []  # records forming the slide currently under construction

    def flush() -> None:
        if not members:
            return
        # Representative = the member with the most tokens (the maximal build
        # frame); ties go to the earliest segment.
        rep = max(members, key=lambda r: (len(r["tokens"]), -r["id"]))
        tokens: set[str] = set().union(*(r["tokens"] for r in members))
        occ = _coalesce([(r["block"].start_t, r["block"].end_t) for r in members], coalesce_gap)
        slides.append(
            Slide(
                index=len(slides) + 1,
                seg_ids=[r["id"] for r in members],
                occurrences=occ,
                rep_frame=rep["frame"],
                text=rep["text"],
                tokens=tokens,
            )
        )

    for r in records:
        toks = r["tokens"]
        if not members:
            decisions.append(MergeDecision(r["id"], "first", 0.0, 0.0))
            members = [r]
            continue

        current: set[str] = set().union(*(m["tokens"] for m in members))
        cur_in_new = containment(current, toks)  # current subset of new?
        new_in_cur = containment(toks, current)  # new subset of current?

        if len(toks) < min_tokens or len(current) < min_tokens:
            relation = "low_text"
        elif cur_in_new >= overlap and new_in_cur >= overlap:
            relation = "equal"
        elif cur_in_new >= overlap:  # current ⊆ new and new has more -> build
            relation = "build"
        else:
            relation = "new"

        decisions.append(
            MergeDecision(r["id"], relation, round(cur_in_new, 3), round(new_in_cur, 3))
        )

        if relation in ("equal", "build"):
            members.append(r)
        else:
            flush()
            members = [r]

    flush()
    return slides, decisions
