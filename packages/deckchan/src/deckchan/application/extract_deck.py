from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from deckchan.adapters.diagnostic_plot import write_difference_plot
from deckchan.adapters.pdf_deck_writer import PdfDeckWriter
from deckchan.adapters.pptx_deck_writer import PptxDeckWriter
from deckchan.config import DeckConfig
from deckchan.domain.slide import Slide, SlideCandidate, SlideMergeDecision, merge_slides
from framechan.adapters.ffmpeg_frame_source import FfmpegFrameSource
from framechan.adapters.tesseract_recognizer import TesseractRecognizer
from framechan.application.extract_segments import ExtractedSegments, recognized_text_to_dict
from framechan.config import FrameConfig
from framechan.domain.difference import DifferenceSeries
from framechan.domain.segment import Segment
from framechan.ports.frame_source import FrameSource
from framechan.ports.text_recognizer import TextRecognizer
from framechan.trace import write_trace


@dataclass(frozen=True)
class DeckResult:
    video: Path
    out_dir: Path
    threshold: float
    n_segments_total: int
    n_segments_captured: int
    slides: list[Slide]
    deck_pdf: Path
    deck_pptx: Path | None
    trace_path: Path
    plot_path: Path
    timeline: str

    def print_summary(self) -> None:
        print(f"\ndeckchan - {self.video.name}")
        print(f"  static threshold ......... {self.threshold:.4f}")
        print(
            f"  static segments .......... {self.n_segments_captured} captured "
            f"/ {self.n_segments_total} total"
        )
        print(f"  slides ................... {len(self.slides)}")
        print(f"\n  timeline: {self.timeline}\n")
        for slide in self.slides:
            occ = ", ".join(f"{a:.1f}-{b:.1f}s" for a, b in slide.occurrences)
            preview = " ".join(slide.text.split())[:60] or "(no text)"
            print(f"   slide {slide.index:>2}  [{occ}]  {preview!r}")
        print(f"\n  deck:  {self.deck_pdf}")
        if self.deck_pptx:
            print(f"  pptx:  {self.deck_pptx}")
        print(f"  trace: {self.trace_path}")
        print(f"  plot:  {self.plot_path}\n")


def _extract_segments_with_source(
    video: Path,
    frame_config: FrameConfig,
    source: FrameSource,
    recognizer: TextRecognizer,
) -> ExtractedSegments:
    from framechan.application.extract_segments import extract_segments

    return extract_segments(video, frame_config, frame_source=source, recognizer=recognizer)


def _save_representative_frames(
    source: FrameSource,
    segments: ExtractedSegments,
    frames_dir: Path,
) -> dict[int, Path]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[int, Path] = {}
    for segment_text in segments.texts:
        segment = segment_text.segment
        path = frames_dir / f"seg{segment.index:03d}.png"
        source.frame_at(segment.representative_t).save(path)
        paths[segment.index] = path
    return paths


def _timeline(slides: list[Slide], series: DifferenceSeries, eps: float) -> str:
    spans = sorted((a, b, slide.index) for slide in slides for a, b in slide.occurrences)
    parts: list[str] = []
    cursor = 0.0
    for start, end, index in spans:
        if start - cursor > eps:
            parts.append(f"GAP[{cursor:.1f}-{start:.1f}]")
        parts.append(f"S{index}[{start:.1f}-{end:.1f}]")
        cursor = max(cursor, end)
    total_t = float(series.times[-1]) if series.times else 0.0
    if total_t - cursor > eps:
        parts.append(f"GAP[{cursor:.1f}-{total_t:.1f}]")
    return "  ·  ".join(parts)


def _trace_payload(
    video: Path,
    config: DeckConfig,
    extracted: ExtractedSegments,
    decisions: list[SlideMergeDecision],
    slides: list[Slide],
    timeline: str,
) -> dict:
    text_by_segment = {text.segment.index: text for text in extracted.texts}
    return {
        "tool": "deckchan",
        "video": str(video),
        "config": {"frame": config.frame.to_dict(), "make_pptx": config.make_pptx},
        "sampling": {
            "fps": extracted.series.fps,
            "n_frames": extracted.series.size,
            "diff_resolution": f"{config.frame.diff_width}x{config.frame.diff_height}",
        },
        "static_threshold": extracted.threshold,
        "difference_series": [
            {
                "i": i,
                "t": round(extracted.series.times[i], 3),
                "diff": round(extracted.series.diffs[i], 5),
                "static": extracted.series.diffs[i] < extracted.threshold,
            }
            for i in range(extracted.series.size)
        ],
        "segments": [_segment_payload(segment, text_by_segment) for segment in extracted.segments],
        "merge_decisions": [
            {
                "segment": decision.segment,
                "relation": decision.relation,
                "current_subset_of_new": decision.current_subset_of_new,
                "new_subset_of_current": decision.new_subset_of_current,
            }
            for decision in decisions
        ],
        "slides": [
            {
                "index": slide.index,
                "from_segments": list(slide.source_segments),
                "occurrences": [[round(a, 2), round(b, 2)] for a, b in slide.occurrences],
                "rep_frame": str(slide.representative_frame),
                "n_tokens": len(slide.tokens),
                "recognized_text": slide.text,
            }
            for slide in slides
        ],
        "timeline": timeline,
    }


def _segment_payload(segment: Segment, text_by_segment: dict[int, object]) -> dict:
    segment_text = text_by_segment.get(segment.index)
    recognized = None
    n_tokens = None
    if segment_text is not None:
        recognized = recognized_text_to_dict(segment_text.recognized)  # type: ignore[attr-defined]
        n_tokens = len(segment_text.tokens)  # type: ignore[attr-defined]
    return {
        "index": segment.index,
        "start_t": round(segment.start_t, 3),
        "end_t": round(segment.end_t, 3),
        "duration": round(segment.duration, 3),
        "n_samples": segment.n_samples,
        "captured": segment.passed,
        "representative_t": round(segment.representative_t, 3) if segment.passed else None,
        "n_tokens": n_tokens,
        "recognized": recognized,
    }


def extract_deck(
    video: str | Path,
    out_dir: str | Path,
    config: DeckConfig,
    frame_source: FrameSource | None = None,
    recognizer: TextRecognizer | None = None,
) -> DeckResult:
    video_path = Path(video)
    out = Path(out_dir)
    source = frame_source or FfmpegFrameSource(video_path)
    text_recognizer = recognizer or TesseractRecognizer(config.frame.ocr_lang, config.frame.ocr_psm)

    extracted = _extract_segments_with_source(video_path, config.frame, source, text_recognizer)
    frame_paths = _save_representative_frames(source, extracted, out / "frames")
    candidates = [
        SlideCandidate(segment_text=text, representative_frame=frame_paths[text.segment.index])
        for text in extracted.texts
    ]
    slides, decisions = merge_slides(
        candidates,
        config.frame.text_overlap,
        config.frame.min_text_tokens,
        coalesce_gap=2.0 / config.frame.sample_fps,
    )

    deck_pdf = out / "deck.pdf"
    PdfDeckWriter().write(slides, deck_pdf)
    deck_pptx = out / "deck.pptx" if config.make_pptx else None
    if deck_pptx:
        PptxDeckWriter().write(slides, deck_pptx)

    plot_path = out / "diff_series.png"
    write_difference_plot(extracted.series, extracted.threshold, extracted.segments, plot_path)
    timeline = _timeline(slides, extracted.series, eps=1.0 / config.frame.sample_fps)
    trace_path = out / "trace.json"
    write_trace(_trace_payload(video_path, config, extracted, decisions, slides, timeline), trace_path)

    return DeckResult(
        video=video_path,
        out_dir=out,
        threshold=extracted.threshold,
        n_segments_total=len(extracted.segments),
        n_segments_captured=len(extracted.captured_segments),
        slides=slides,
        deck_pdf=deck_pdf,
        deck_pptx=deck_pptx,
        trace_path=trace_path,
        plot_path=plot_path,
        timeline=timeline,
    )
