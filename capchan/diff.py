"""Stage 1 — the difference signal.

We let ffmpeg do the expensive decoding and temporal subsampling, then read a
stream of tiny downscaled grayscale frames and reduce them to a single number
per sampled frame: the mean absolute difference from the previous frame.

The resulting series is piecewise-stationary by nature: long plateaus near zero
while a slide sits there, brief spikes at cuts/builds, and sustained elevation
during talking-head or B-roll footage. Every later stage reads off this shape.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

import numpy as np


@dataclass
class DiffSeries:
    fps: float
    width: int
    height: int
    times: np.ndarray  # (N,) seconds, one entry per sampled frame
    diffs: np.ndarray  # (N,) mean abs difference from previous frame, in [0, 1]; diffs[0] = 0


def sample_diff_series(
    video, fps: float = 2.0, width: int = 96, height: int = 54
) -> DiffSeries:
    """Decode `video` at `fps`, downscaled to `width`x`height` grayscale, and
    return the inter-frame difference series.

    Downscaling makes the signal robust to codec noise and cheap to compute; the
    forced size distorts aspect ratio, which is irrelevant because every frame is
    distorted identically and we only ever compare frame to frame.
    """
    cmd = [
        "ffmpeg", "-i", str(video),
        "-vf", f"fps={fps},scale={width}:{height},format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray",
        "-v", "error", "pipe:1",
    ]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout

    frame_bytes = width * height
    n = len(raw) // frame_bytes
    if n == 0:
        raise RuntimeError(f"ffmpeg decoded no frames from {video!r}")
    frames = (
        np.frombuffer(raw[: n * frame_bytes], dtype=np.uint8)
        .reshape(n, height, width)
        .astype(np.float32)
    )

    diffs = np.zeros(n, dtype=np.float64)
    if n > 1:
        diffs[1:] = np.abs(np.diff(frames, axis=0)).reshape(n - 1, -1).mean(axis=1) / 255.0
    times = np.arange(n, dtype=np.float64) / fps

    return DiffSeries(fps=fps, width=width, height=height, times=times, diffs=diffs)
