"""The pipeline — wire the four stages together and emit deck + trace.

  sample the difference series
    -> threshold it (Otsu, or an override) and cut into static segments
    -> for each segment that clears the duration floor, grab a frame and OCR it
    -> collapse segments into slides by text identity
    -> render the deck, the diagnostic plot, and a full JSON trace.

The trace is the point of the whole thing for v1: when a slide goes missing on a
real video, it tells you *why* — gated out (loosen the gate / lower the floor) or
text-merged into a neighbour (tighten the overlap) — so tuning is a glance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image

from .config import Config
from .deck import build_pdf, build_pptx, extract_frame, plot_diff
from .diff import sample_diff_series
from .identity import Slide, merge_segments
from .ocr import OCRBackend, TesseractBackend, tokenize
from .segment import auto_threshold, find_static_segments


@dataclass
class Result:
    video: Path
    out_dir: Path
    threshold: float
    n_segments_total: int
    n_segments_captured: int
    slides: list
    deck_pdf: Path
    deck_pptx: Optional[Path]
    trace_path: Path
    plot_path: Path
    timeline: str

    def print_summary(self) -> None:
        print(f"\ncapchan - {self.video.name}")
        print(f"  static threshold ......... {self.threshold:.4f}")
        print(
            f"  static segments .......... {self.n_segments_captured} captured "
            f"/ {self.n_segments_total} total"
        )
        print(f"  slides ................... {len(self.slides)}")
        print(f"\n  timeline: {self.timeline}\n")
        for s in self.slides:
            occ = ", ".join(f"{a:.1f}-{b:.1f}s" for a, b in s.occurrences)
            preview = " ".join(s.text.split())[:60] or "(no text)"
            print(f"   slide {s.index:>2}  [{occ}]  {preview!r}")
        print(f"\n  deck:  {self.deck_pdf}")
        if self.deck_pptx:
            print(f"  pptx:  {self.deck_pptx}")
        print(f"  trace: {self.trace_path}")
        print(f"  plot:  {self.plot_path}\n")


def _timeline(slides, total_t: float, eps: float) -> str:
    spans = sorted(
        (a, b, s.index) for s in slides for a, b in s.occurrences
    )
    parts: list[str] = []
    cursor = 0.0
    for a, b, idx in spans:
        if a - cursor > eps:
            parts.append(f"GAP[{cursor:.1f}-{a:.1f}]")
        parts.append(f"S{idx}[{a:.1f}-{b:.1f}]")
        cursor = max(cursor, b)
    if total_t - cursor > eps:
        parts.append(f"GAP[{cursor:.1f}-{total_t:.1f}]")
    return "  ·  ".join(parts)


def build_trace(video, cfg, series, threshold, segments, records, decisions, slides, timeline) -> dict:
    rec_by_id = {r["id"]: r for r in records}
    return {
        "video": str(video),
        "config": cfg.to_dict(),
        "sampling": {
            "fps": series.fps,
            "n_frames": int(series.diffs.size),
            "diff_resolution": f"{series.width}x{series.height}",
        },
        "static_threshold": threshold,
        "difference_series": [
            {
                "i": i,
                "t": round(float(series.times[i]), 3),
                "diff": round(float(series.diffs[i]), 5),
                "static": bool(series.diffs[i] < threshold),
            }
            for i in range(series.diffs.size)
        ],
        "segments": [
            {
                "id": s.id,
                "start_t": round(s.start_t, 3),
                "end_t": round(s.end_t, 3),
                "duration": round(s.duration, 3),
                "n_frames": s.n_samples,
                "captured": s.passed,
                "rep_t": round(s.rep_t, 3) if s.passed else None,
                "n_tokens": len(rec_by_id[s.id]["tokens"]) if s.id in rec_by_id else None,
                "ocr_text": rec_by_id[s.id]["text"] if s.id in rec_by_id else None,
            }
            for s in segments
        ],
        "merge_decisions": [
            {
                "segment": d.seg_id,
                "relation": d.relation,
                "current_subset_of_new": d.current_in_new,
                "new_subset_of_current": d.new_in_current,
            }
            for d in decisions
        ],
        "slides": [
            {
                "index": s.index,
                "from_segments": s.seg_ids,
                "occurrences": [[round(a, 2), round(b, 2)] for a, b in s.occurrences],
                "rep_frame": str(s.rep_frame),
                "n_tokens": len(s.tokens),
                "ocr_text": s.text,
            }
            for s in slides
        ],
        "timeline": timeline,
    }


def run(
    video,
    out_dir,
    config: Config,
    make_pptx: bool = False,
    ocr_backend: Optional[OCRBackend] = None,
) -> Result:
    video = Path(video)
    out = Path(out_dir)
    (out / "frames").mkdir(parents=True, exist_ok=True)

    # 1 — difference signal
    series = sample_diff_series(video, config.sample_fps, config.diff_width, config.diff_height)

    # 2 — stationarity gate
    if config.static_threshold == "auto":
        threshold = auto_threshold(series.diffs[1:])  # drop the forced diffs[0] = 0
    else:
        threshold = float(config.static_threshold)
    segments = find_static_segments(series, threshold, config.min_slide_seconds)
    captured = [s for s in segments if s.passed]

    # 3 — OCR each captured segment's representative frame
    ocr = ocr_backend or TesseractBackend(lang=config.ocr_lang, psm=config.ocr_psm)
    records = []
    for s in captured:
        frame_path = out / "frames" / f"seg{s.id:03d}.png"
        extract_frame(video, s.rep_t, frame_path)
        with Image.open(frame_path) as im:
            text = ocr.text(im)
        records.append(
            {
                "id": s.id,
                "block": s,
                "frame": frame_path,
                "text": " ".join(text.split()),
                "tokens": tokenize(text),
            }
        )

    # 4 — text identity
    coalesce_gap = 2.0 / config.sample_fps
    slides, decisions = merge_segments(
        records, config.text_overlap, config.min_text_tokens, coalesce_gap
    )

    # outputs
    rep_frames = [s.rep_frame for s in slides]
    deck_pdf = out / "deck.pdf"
    build_pdf(rep_frames, deck_pdf)
    deck_pptx: Optional[Path] = None
    if make_pptx and rep_frames:
        deck_pptx = out / "deck.pptx"
        build_pptx(rep_frames, deck_pptx)

    plot_path = out / "diff_series.png"
    plot_diff(series, threshold, segments, plot_path)

    total_t = float(series.times[-1]) if series.times.size else 0.0
    timeline = _timeline(slides, total_t, eps=1.0 / config.sample_fps)
    trace = build_trace(
        video, config, series, threshold, segments, records, decisions, slides, timeline
    )
    trace_path = out / "trace.json"
    trace_path.write_text(json.dumps(trace, indent=2))

    return Result(
        video=video,
        out_dir=out,
        threshold=threshold,
        n_segments_total=len(segments),
        n_segments_captured=len(captured),
        slides=slides,
        deck_pdf=deck_pdf,
        deck_pptx=deck_pptx,
        trace_path=trace_path,
        plot_path=plot_path,
        timeline=timeline,
    )
