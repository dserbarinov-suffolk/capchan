from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from framechan.domain.difference import DifferenceSeries
from framechan.domain.segment import Segment


def write_difference_plot(
    series: DifferenceSeries,
    threshold: float,
    segments: tuple[Segment, ...],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.plot(series.times, series.diffs, lw=0.8, color="#333333", label="frame-to-frame difference")
    ax.axhline(
        threshold,
        color="#c0392b",
        lw=1.0,
        ls="--",
        label=f"static threshold = {threshold:.4f}",
    )

    labelled = {"captured": False, "short": False}
    for segment in segments:
        if segment.passed:
            ax.axvspan(
                segment.start_t,
                segment.end_t,
                color="#2ecc71",
                alpha=0.25,
                label=None if labelled["captured"] else "captured static segment",
            )
            labelled["captured"] = True
        elif segment.end_t > segment.start_t:
            ax.axvspan(
                segment.start_t,
                segment.end_t,
                color="#bdc3c7",
                alpha=0.35,
                label=None if labelled["short"] else "static but too short",
            )
            labelled["short"] = True

    ax.set_xlabel("time (s)")
    ax.set_ylabel("mean abs diff (0-1)")
    ax.set_title("Difference series and stationarity gate")
    ax.margins(x=0.005)
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
