from __future__ import annotations

import argparse
from pathlib import Path

from framechan.config import FrameConfig
from subchan.application.extract_subtitles import extract_subtitles
from subchan.config import SubConfig

BOTTOM_THIRD_TOP = 2.0 / 3.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="subchan",
        description="Turn burned-in subtitles into SRT/VTT plus an inspectable trace.",
    )
    parser.add_argument("video", type=Path, help="input video")
    parser.add_argument("-o", "--out", type=Path, default=Path("out"), help="output directory")
    parser.add_argument("--vtt", action="store_true", help="also emit captions.vtt")
    parser.add_argument("--mode", choices=("banded", "full-frame"), default="banded")
    parser.add_argument(
        "--bottom-third",
        action="store_true",
        help="only OCR the lower third of each selected frame",
    )
    parser.add_argument(
        "--ocr-engine",
        choices=("auto", "tesseract", "vision"),
        default=SubConfig.ocr_engine,
        help="text recognition backend; auto uses Vision on macOS when installed, otherwise Tesseract",
    )
    parser.add_argument("--band-top", type=float, default=SubConfig.band_top)
    parser.add_argument("--band-bottom", type=float, default=SubConfig.band_bottom)
    parser.add_argument(
        "--conditioning",
        choices=("brightness", "subtitle-outline", "none"),
        default=SubConfig.conditioning,
    )
    parser.add_argument("--brightness-threshold", type=int, default=SubConfig.brightness_threshold)
    parser.add_argument("--fps", type=float, default=FrameConfig.sample_fps)
    parser.add_argument("--static-threshold", default="auto")
    parser.add_argument("--min-seconds", type=float, default=FrameConfig.min_segment_seconds)
    parser.add_argument("--ocr-lang", default=FrameConfig.ocr_lang)
    parser.add_argument("--ocr-psm", type=int, default=6)
    args = parser.parse_args(argv)

    threshold = args.static_threshold
    if threshold != "auto":
        threshold = float(threshold)

    mode = args.mode
    band_top = args.band_top
    band_bottom = args.band_bottom
    if args.bottom_third:
        mode = "banded"
        band_top = BOTTOM_THIRD_TOP
        band_bottom = 1.0

    frame = FrameConfig(
        sample_fps=args.fps,
        static_threshold=threshold,
        min_segment_seconds=args.min_seconds,
        ocr_lang=args.ocr_lang,
        ocr_psm=args.ocr_psm,
    )
    config = SubConfig(
        frame=frame,
        mode=mode,
        ocr_engine=args.ocr_engine,
        band_top=band_top,
        band_bottom=band_bottom,
        conditioning=args.conditioning,
        brightness_threshold=args.brightness_threshold,
        make_vtt=args.vtt,
    )
    result = extract_subtitles(args.video, args.out, config)
    result.print_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
