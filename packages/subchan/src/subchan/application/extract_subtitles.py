from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

from framechan.adapters.ffmpeg_frame_source import FfmpegFrameSource
from framechan.adapters.tesseract_recognizer import TesseractRecognizer
from framechan.application.extract_segments import ExtractedSegments, extract_segments
from framechan.ports.frame_source import FrameSource
from framechan.ports.text_recognizer import TextRecognizer
from framechan.trace import write_trace
from subchan.adapters.srt_writer import SrtSubtitleWriter
from subchan.adapters.vtt_writer import VttSubtitleWriter
from subchan.config import SubConfig
from subchan.domain.caption import CaptionCandidate, CaptionEvent
from subchan.domain.discriminate import CaptionDiscriminationResult, discriminate_caption
from subchan.domain.events import EventMergeDecision, merge_events


@dataclass(frozen=True)
class SubtitleResult:
    video: Path
    out_dir: Path
    threshold: float
    n_segments_total: int
    n_segments_captured: int
    events: list[CaptionEvent]
    srt_path: Path
    vtt_path: Path | None
    trace_path: Path

    def print_summary(self) -> None:
        print(f"\nsubchan - {self.video.name}")
        print(f"  static threshold ......... {self.threshold:.4f}")
        print(
            f"  static segments .......... {self.n_segments_captured} captured "
            f"/ {self.n_segments_total} total"
        )
        print(f"  caption events ........... {len(self.events)}")
        for event in self.events[:20]:
            preview = " ".join(event.text.split())[:70]
            print(f"   {event.index:>3}  [{event.start_t:.1f}-{event.end_t:.1f}s]  {preview!r}")
        if len(self.events) > 20:
            print(f"   ... {len(self.events) - 20} more")
        print(f"\n  srt:   {self.srt_path}")
        if self.vtt_path:
            print(f"  vtt:   {self.vtt_path}")
        print(f"  trace: {self.trace_path}\n")


def _condition_image(image: Image.Image, config: SubConfig) -> Image.Image:
    working = image
    if config.mode == "banded":
        width, height = working.size
        top = int(height * config.band_top)
        bottom = int(height * config.band_bottom)
        working = working.crop((0, top, width, bottom))
    gray = ImageOps.grayscale(working)
    if config.brightness_threshold > 0:
        gray = gray.filter(ImageFilter.MedianFilter(3))
        gray = gray.point(lambda value: 255 if value >= config.brightness_threshold else 0)
        gray = gray.filter(ImageFilter.MaxFilter(3))
    return gray


def _caption_candidates(
    extracted: ExtractedSegments,
    config: SubConfig,
) -> tuple[list[CaptionCandidate], list[CaptionDiscriminationResult]]:
    candidates: list[CaptionCandidate] = []
    discriminations: list[CaptionDiscriminationResult] = []
    for segment_text in extracted.texts:
        segment = segment_text.segment
        result = discriminate_caption(
            segment_text.recognized,
            mode=config.mode,
            segment_duration=segment.duration,
            min_confidence=config.min_confidence,
            min_box_height=config.min_box_height,
            max_box_height=config.max_box_height,
        )
        discriminations.append(result)
        if result.text.strip():
            candidates.append(
                CaptionCandidate(
                    segment=segment.index,
                    start_t=segment.start_t,
                    end_t=segment.end_t,
                    text=result.text,
                )
            )
    return candidates, discriminations


def _trace_payload(
    video: Path,
    config: SubConfig,
    extracted: ExtractedSegments,
    candidates: list[CaptionCandidate],
    discriminations: list[CaptionDiscriminationResult],
    decisions: list[EventMergeDecision],
    events: list[CaptionEvent],
) -> dict:
    text_by_segment = {text.segment.index: text for text in extracted.texts}
    disc_by_segment = {
        text.segment.index: discriminations[i]
        for i, text in enumerate(extracted.texts)
        if i < len(discriminations)
    }
    return {
        "tool": "subchan",
        "video": str(video),
        "config": {
            "frame": config.frame.to_dict(),
            "mode": config.mode,
            "band_top": config.band_top,
            "band_bottom": config.band_bottom,
            "brightness_threshold": config.brightness_threshold,
            "make_vtt": config.make_vtt,
        },
        "static_threshold": extracted.threshold,
        "sampling": {
            "fps": extracted.series.fps,
            "n_frames": extracted.series.size,
            "diff_resolution": f"{config.frame.diff_width}x{config.frame.diff_height}",
        },
        "segments": [
            {
                "index": segment.index,
                "start_t": round(segment.start_t, 3),
                "end_t": round(segment.end_t, 3),
                "duration": round(segment.duration, 3),
                "n_samples": segment.n_samples,
                "captured": segment.passed,
                "representative_t": round(segment.representative_t, 3) if segment.passed else None,
                "recognized_text": (
                    text_by_segment[segment.index].recognized.text
                    if segment.index in text_by_segment
                    else None
                ),
                "caption_text": (
                    disc_by_segment[segment.index].text
                    if segment.index in disc_by_segment
                    else None
                ),
                "caption_box_decisions": [
                    {
                        "text": decision.text,
                        "confidence": decision.confidence,
                        "bbox": list(decision.bbox),
                        "score": decision.score,
                        "kept": decision.kept,
                        "reasons": list(decision.reasons),
                    }
                    for decision in (
                        disc_by_segment[segment.index].decisions
                        if segment.index in disc_by_segment
                        else ()
                    )
                ],
            }
            for segment in extracted.segments
        ],
        "caption_candidates": [
            {
                "segment": candidate.segment,
                "start_t": round(candidate.start_t, 3),
                "end_t": round(candidate.end_t, 3),
                "text": candidate.text,
            }
            for candidate in candidates
        ],
        "merge_decisions": [
            {
                "segment": decision.segment,
                "relation": decision.relation,
                "current_subset_of_new": decision.current_subset_of_new,
                "new_subset_of_current": decision.new_subset_of_current,
            }
            for decision in decisions
        ],
        "events": [
            {
                "index": event.index,
                "start_t": round(event.start_t, 3),
                "end_t": round(event.end_t, 3),
                "text": event.text,
            }
            for event in events
        ],
    }


def extract_subtitles(
    video: str | Path,
    out_dir: str | Path,
    config: SubConfig,
    frame_source: FrameSource | None = None,
    recognizer: TextRecognizer | None = None,
) -> SubtitleResult:
    video_path = Path(video)
    out = Path(out_dir)
    source = frame_source or FfmpegFrameSource(video_path)
    text_recognizer = recognizer or TesseractRecognizer(config.frame.ocr_lang, config.frame.ocr_psm)

    extracted = extract_segments(
        video_path,
        config.frame,
        frame_source=source,
        recognizer=text_recognizer,
        image_transform=lambda image: _condition_image(image, config),
    )
    candidates, discriminations = _caption_candidates(extracted, config)
    events, decisions = merge_events(candidates, config.same_text_overlap, config.max_merge_gap)

    srt_path = out / "captions.srt"
    SrtSubtitleWriter().write(events, srt_path)
    vtt_path = out / "captions.vtt" if config.make_vtt else None
    if vtt_path:
        VttSubtitleWriter().write(events, vtt_path)

    trace_path = out / "trace.json"
    write_trace(
        _trace_payload(video_path, config, extracted, candidates, discriminations, decisions, events),
        trace_path,
    )
    return SubtitleResult(
        video=video_path,
        out_dir=out,
        threshold=extracted.threshold,
        n_segments_total=len(extracted.segments),
        n_segments_captured=len(extracted.captured_segments),
        events=events,
        srt_path=srt_path,
        vtt_path=vtt_path,
        trace_path=trace_path,
    )
