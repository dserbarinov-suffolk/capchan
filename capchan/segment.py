"""Stage 2 — the stationarity gate (slide-vs-not).

A slide is a held still frame: a run of consecutive sampled frames each nearly
identical to the one before. A cut, a build step, or a stretch of talking-head
motion all produce above-threshold differences that break such a run.

The only question is "above what?" — and the answer is read from the video's own
difference histogram with Otsu's method, which finds the valley between the
near-zero (static) mode and the elevated (motion) mode. No per-video constant.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .diff import DiffSeries


def otsu_threshold(values: np.ndarray, bins: int = 256) -> float:
    """Classic Otsu: the cutoff that maximises between-class variance.

    For our difference series this separates "static" from "moving" without a
    hand-set number. If the series has no variation (a single still image for the
    whole video) we return a value just above the max, so everything reads as
    static and collapses to one slide.
    """
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return 0.0
    lo, hi = float(v.min()), float(v.max())
    if hi <= lo:
        return float(np.nextafter(hi, hi + 1.0))

    hist, edges = np.histogram(v, bins=bins, range=(lo, hi))
    hist = hist.astype(np.float64)
    total = hist.sum()
    mids = (edges[:-1] + edges[1:]) / 2.0

    weight_bg = np.cumsum(hist)
    weight_fg = total - weight_bg
    sum_bg = np.cumsum(hist * mids)
    sum_all = sum_bg[-1]

    eps = 1e-12
    mean_bg = sum_bg / (weight_bg + eps)
    mean_fg = (sum_all - sum_bg) / (weight_fg + eps)
    between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
    return float(mids[int(np.argmax(between))])


def auto_threshold(diffs: np.ndarray) -> float:
    """Pick the static/motion cutoff from the difference series.

    Held frames cluster tightly at ~0 while motion spreads over a long upper
    tail. Plain Otsu, maximising between-class variance, will carve that tail
    (isolating the busiest frames) instead of separating it from zero. Running
    Otsu in log space compresses the tail and expands the near-zero region, so
    the dominant split is exactly static-vs-moving. The floor keeps the log
    finite for held frames and encodes "below a quarter of a gray level, two
    frames are identical" — a property of 8-bit video, not of any one clip.
    """
    floor = 1e-3
    d = np.asarray(diffs, dtype=np.float64)
    d = d[np.isfinite(d)]
    if d.size == 0:
        return 0.0
    log_t = otsu_threshold(np.log10(np.clip(d, 0.0, None) + floor))
    return max(0.0, float(10.0 ** log_t - floor))


@dataclass
class Segment:
    """A maximal run of consecutive sampled frames held still together."""

    id: int
    start_i: int
    end_i: int
    start_t: float
    end_t: float
    n_samples: int
    passed: bool  # cleared the minimum-duration floor (i.e. is a slide candidate)
    rep_t: float  # time of the representative frame (see find_static_segments)

    @property
    def duration(self) -> float:
        return self.end_t - self.start_t


def find_static_segments(
    series: DiffSeries, threshold: float, min_seconds: float
) -> list[Segment]:
    """Split the timeline into static blocks and flag which clear the duration floor.

    A difference at index i that meets or exceeds the threshold is a boundary
    between frame i-1 and frame i. Everything between two boundaries is one block.
    Sustained motion produces many tiny blocks that fail the floor; a held slide
    produces one long block that passes.
    """
    d = series.diffs
    t = series.times
    n = d.size

    boundaries: list[tuple[int, int]] = []
    start = 0
    for i in range(1, n):
        if d[i] >= threshold:
            boundaries.append((start, i - 1))
            start = i
    boundaries.append((start, n - 1))

    half_step = 0.5 / series.fps
    segments: list[Segment] = []
    for sid, (a, b) in enumerate(boundaries):
        start_t, end_t = float(t[a]), float(t[b])
        # Represent the block by its LAST held frame, backed off half a sample to
        # stay clear of the exit transition. For a progressively built slide that
        # final frame carries every bullet that appeared; for a plain held slide
        # any interior frame is equivalent. This is what lets a build the gate did
        # not split still come out complete.
        rep_t = max(start_t, end_t - half_step)
        segments.append(
            Segment(
                id=sid,
                start_i=a,
                end_i=b,
                start_t=start_t,
                end_t=end_t,
                n_samples=b - a + 1,
                passed=(end_t - start_t) >= min_seconds,
                rep_t=rep_t,
            )
        )
    return segments
