"""Command-line entry point.

The defaults come straight from Config. The two flags worth knowing for the
tuning pass are --static-threshold (swap Otsu for an absolute cutoff) and
--min-seconds (lower the duration floor if short slides are being dropped).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from .config import Config
from .pipeline import run


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(
        prog="capchan",
        description="Turn a slide-deck-style video into a deck plus an inspectable trace.",
    )
    p.add_argument("video", type=Path, help="input video (anything ffmpeg can read)")
    p.add_argument("-o", "--out", type=Path, default=Path("out"),
                   help="output directory (default: out)")
    p.add_argument("--pptx", action="store_true",
                   help="also emit deck.pptx (deck.pdf is always emitted)")
    p.add_argument("--fps", type=float, default=Config.sample_fps,
                   help="frame sampling rate for the difference signal")
    p.add_argument("--static-threshold", default="auto",
                   help='"auto" (Otsu, per-video) or an absolute 0-1 cutoff for tuning')
    p.add_argument("--min-seconds", type=float, default=Config.min_slide_seconds,
                   help="minimum on-screen time to count as a slide")
    p.add_argument("--text-overlap", type=float, default=Config.text_overlap,
                   help="token-containment cutoff for same-slide / build merge")
    p.add_argument("--min-text-tokens", type=int, default=Config.min_text_tokens,
                   help="below this a segment is low-text and is never merged")
    args = p.parse_args(argv)

    threshold = args.static_threshold
    if threshold != "auto":
        threshold = float(threshold)

    cfg = Config(
        sample_fps=args.fps,
        static_threshold=threshold,
        min_slide_seconds=args.min_seconds,
        text_overlap=args.text_overlap,
        min_text_tokens=args.min_text_tokens,
    )
    result = run(args.video, args.out, cfg, make_pptx=args.pptx)
    result.print_summary()
    return 0
