from __future__ import annotations

import argparse
from pathlib import Path

from deckchan.application.extract_deck import extract_deck
from deckchan.config import DeckConfig
from framechan.config import FrameConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="deckchan",
        description="Turn a slide-style video into a deck plus an inspectable trace.",
    )
    parser.add_argument("video", type=Path, help="input video")
    parser.add_argument("-o", "--out", type=Path, default=Path("out"), help="output directory")
    parser.add_argument("--pptx", action="store_true", help="also emit deck.pptx")
    parser.add_argument("--fps", type=float, default=FrameConfig.sample_fps)
    parser.add_argument("--static-threshold", default="auto")
    parser.add_argument("--min-seconds", type=float, default=FrameConfig.min_segment_seconds)
    parser.add_argument("--text-overlap", type=float, default=FrameConfig.text_overlap)
    parser.add_argument("--min-text-tokens", type=int, default=FrameConfig.min_text_tokens)
    parser.add_argument("--ocr-lang", default=FrameConfig.ocr_lang)
    parser.add_argument("--ocr-psm", type=int, default=FrameConfig.ocr_psm)
    args = parser.parse_args(argv)

    threshold = args.static_threshold
    if threshold != "auto":
        threshold = float(threshold)

    frame = FrameConfig(
        sample_fps=args.fps,
        static_threshold=threshold,
        min_segment_seconds=args.min_seconds,
        text_overlap=args.text_overlap,
        min_text_tokens=args.min_text_tokens,
        ocr_lang=args.ocr_lang,
        ocr_psm=args.ocr_psm,
    )
    result = extract_deck(args.video, args.out, DeckConfig(frame=frame, make_pptx=args.pptx))
    result.print_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
