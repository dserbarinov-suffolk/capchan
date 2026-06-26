from __future__ import annotations

import math

from .difference import DifferenceSeries
from .segment import Segment


def otsu_threshold(values: tuple[float, ...] | list[float], bins: int = 256) -> float:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return 0.0
    lo, hi = min(finite), max(finite)
    if hi <= lo:
        return math.nextafter(hi, hi + 1.0)

    width = (hi - lo) / bins
    hist = [0.0] * bins
    for value in finite:
        index = min(bins - 1, int((value - lo) / width))
        hist[index] += 1.0
    total = sum(hist)
    mids = [lo + (i + 0.5) * width for i in range(bins)]

    sum_all = sum(count * mid for count, mid in zip(hist, mids))
    weight_bg = 0.0
    sum_bg = 0.0
    best_index = 0
    best_between = -1.0

    eps = 1e-12
    for index, (count, mid) in enumerate(zip(hist, mids)):
        weight_bg += count
        sum_bg += count * mid
        weight_fg = total - weight_bg
        mean_bg = sum_bg / (weight_bg + eps)
        mean_fg = (sum_all - sum_bg) / (weight_fg + eps)
        between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if between > best_between:
            best_between = between
            best_index = index
    return mids[best_index]


def auto_threshold(diffs: tuple[float, ...] | list[float]) -> float:
    floor = 1e-3
    finite = [float(value) for value in diffs if math.isfinite(float(value))]
    if not finite:
        return 0.0
    log_t = otsu_threshold([math.log10(max(value, 0.0) + floor) for value in finite])
    return max(0.0, float(10.0**log_t - floor))


def find_segments(series: DifferenceSeries, threshold: float, min_seconds: float) -> list[Segment]:
    if series.size == 0:
        return []

    boundaries: list[tuple[int, int]] = []
    start = 0
    for i in range(1, series.size):
        if series.diffs[i] >= threshold:
            boundaries.append((start, i - 1))
            start = i
    boundaries.append((start, series.size - 1))

    half_step = 0.5 / series.fps
    segments: list[Segment] = []
    for index, (a, b) in enumerate(boundaries):
        start_t = float(series.times[a])
        end_t = float(series.times[b])
        representative_t = max(start_t, end_t - half_step)
        segments.append(
            Segment(
                index=index,
                start_t=start_t,
                end_t=end_t,
                representative_t=representative_t,
                n_samples=b - a + 1,
                passed=(end_t - start_t) >= min_seconds,
            )
        )
    return segments
