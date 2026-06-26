from __future__ import annotations

import importlib.util
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from framechan.adapters.ffmpeg_frame_source import FfmpegFrameSource
from framechan.adapters.tesseract_recognizer import TesseractRecognizer
from framechan.adapters.vision_recognizer import VisionRecognizer
from framechan.application.extract_segments import ExtractedSegments, extract_segments
from framechan.domain.text import RecognizedText
from framechan.ports.frame_source import FrameSource
from framechan.ports.text_recognizer import TextRecognizer
from framechan.trace import write_trace
from subchan.adapters.srt_writer import SrtSubtitleWriter
from subchan.adapters.vtt_writer import VttSubtitleWriter
from subchan.config import SubConfig, TextScript
from subchan.domain.caption import CaptionCandidate, CaptionEvent
from subchan.domain.discriminate import (
    CaptionBoxDecision,
    CaptionDiscriminationResult,
    discriminate_caption,
)
from subchan.domain.events import EventMergeDecision, merge_events


@dataclass(frozen=True)
class SubtitleResult:
    video: Path
    out_dir: Path
    capture_mode: str
    threshold: float | None
    n_segments_total: int
    n_segments_captured: int
    events: list[CaptionEvent]
    srt_path: Path
    vtt_path: Path | None
    trace_path: Path

    def print_summary(self) -> None:
        print(f"\nsubchan - {self.video.name}")
        if self.capture_mode == "scan":
            print(f"  capture mode ............. scan")
            print(
                f"  ocr samples .............. {self.n_segments_captured} with captions "
                f"/ {self.n_segments_total} total"
            )
        else:
            threshold = self.threshold if self.threshold is not None else 0.0
            print(f"  static threshold ......... {threshold:.4f}")
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


@dataclass(frozen=True)
class ScanSample:
    index: int
    start_t: float
    end_t: float
    recognized: RecognizedText
    discrimination: CaptionDiscriminationResult


def _condition_image(image: Image.Image, config: SubConfig) -> Image.Image:
    working = image
    if config.mode == "banded":
        width, height = working.size
        top = int(height * config.band_top)
        bottom = int(height * config.band_bottom)
        working = working.crop((0, top, width, bottom))
    if config.conditioning == "none":
        return working
    if config.conditioning == "subtitle-outline":
        return _outline_caption_mask(working)
    gray = ImageOps.grayscale(working)
    if config.brightness_threshold > 0:
        gray = gray.filter(ImageFilter.MedianFilter(3))
        gray = gray.point(lambda value: 255 if value >= config.brightness_threshold else 0)
        gray = gray.filter(ImageFilter.MaxFilter(3))
    return gray


def _outline_caption_mask(image: Image.Image) -> Image.Image:
    arr = np.asarray(image.convert("RGB"))
    red = arr[:, :, 0]
    green = arr[:, :, 1]
    blue = arr[:, :, 2]
    max_channel = arr.max(axis=2)
    min_channel = arr.min(axis=2)
    white_outline = max_channel > 215
    warm_fill = ((max_channel - min_channel) > 55) & (red > 145) & (green > 70) & (blue < 160)
    mask = white_outline | warm_fill
    output = np.full(mask.shape, 255, dtype=np.uint8)
    output[mask] = 0
    return Image.fromarray(output).filter(ImageFilter.MinFilter(3))


def _caption_candidates(
    extracted: ExtractedSegments,
    config: SubConfig,
) -> tuple[list[CaptionCandidate], list[CaptionDiscriminationResult]]:
    candidates: list[CaptionCandidate] = []
    discriminations: list[CaptionDiscriminationResult] = []
    text_script = _resolve_text_script(config)
    for segment_text in extracted.texts:
        segment = segment_text.segment
        result = discriminate_caption(
            segment_text.recognized,
            mode=config.mode,
            segment_duration=segment.duration,
            min_confidence=config.min_confidence,
            min_box_height=config.min_box_height,
            max_box_height=config.max_box_height,
            text_script=text_script,
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
            "capture_mode": config.capture_mode,
            "mode": config.mode,
            "ocr_engine": config.ocr_engine,
            "text_script": config.text_script,
            "band_top": config.band_top,
            "band_bottom": config.band_bottom,
            "conditioning": config.conditioning,
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
    text_recognizer = recognizer or _build_recognizer(config)
    if config.capture_mode == "scan":
        return _extract_subtitles_by_scan(video_path, out, config, source, text_recognizer)

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
        capture_mode="static",
        threshold=extracted.threshold,
        n_segments_total=len(extracted.segments),
        n_segments_captured=len(extracted.captured_segments),
        events=events,
        srt_path=srt_path,
        vtt_path=vtt_path,
        trace_path=trace_path,
    )


def _extract_subtitles_by_scan(
    video_path: Path,
    out: Path,
    config: SubConfig,
    source: FrameSource,
    recognizer: TextRecognizer,
) -> SubtitleResult:
    text_script = _resolve_text_script(config)
    step = 1.0 / config.frame.sample_fps
    start_t = config.scan_start
    end_t = _scan_end_t(video_path, config)
    samples: list[ScanSample] = []
    candidates: list[CaptionCandidate] = []

    for index, (t, frame) in enumerate(_scan_frames(source, start_t, end_t, config.frame.sample_fps)):
        image = _condition_image(frame, config)
        recognized = recognizer.recognize(image)
        discrimination = discriminate_caption(
            recognized,
            mode=config.mode,
            segment_duration=step,
            min_confidence=config.min_confidence,
            min_box_height=config.min_box_height,
            max_box_height=config.max_box_height,
            text_script=text_script,
        )
        sample_end = min(t + step, end_t)
        sample = ScanSample(index, t, sample_end, recognized, discrimination)
        samples.append(sample)
        if discrimination.text.strip():
            candidates.append(CaptionCandidate(index, t, sample_end, discrimination.text))

    events, decisions = merge_events(candidates, config.same_text_overlap, config.max_merge_gap)
    srt_path = out / "captions.srt"
    SrtSubtitleWriter().write(events, srt_path)
    vtt_path = out / "captions.vtt" if config.make_vtt else None
    if vtt_path:
        VttSubtitleWriter().write(events, vtt_path)

    trace_path = out / "trace.json"
    write_trace(
        _scan_trace_payload(video_path, config, start_t, end_t, samples, candidates, decisions, events),
        trace_path,
    )
    return SubtitleResult(
        video=video_path,
        out_dir=out,
        capture_mode="scan",
        threshold=None,
        n_segments_total=len(samples),
        n_segments_captured=len(candidates),
        events=events,
        srt_path=srt_path,
        vtt_path=vtt_path,
        trace_path=trace_path,
    )


def _scan_trace_payload(
    video: Path,
    config: SubConfig,
    start_t: float,
    end_t: float,
    samples: list[ScanSample],
    candidates: list[CaptionCandidate],
    decisions: list[EventMergeDecision],
    events: list[CaptionEvent],
) -> dict:
    return {
        "tool": "subchan",
        "video": str(video),
        "config": {
            "frame": config.frame.to_dict(),
            "capture_mode": config.capture_mode,
            "mode": config.mode,
            "ocr_engine": config.ocr_engine,
            "text_script": config.text_script,
            "band_top": config.band_top,
            "band_bottom": config.band_bottom,
            "conditioning": config.conditioning,
            "brightness_threshold": config.brightness_threshold,
            "make_vtt": config.make_vtt,
        },
        "scan": {
            "start_t": round(start_t, 3),
            "end_t": round(end_t, 3),
            "fps": config.frame.sample_fps,
            "n_samples": len(samples),
        },
        "samples": [
            {
                "index": sample.index,
                "start_t": round(sample.start_t, 3),
                "end_t": round(sample.end_t, 3),
                "recognized_text": sample.recognized.text,
                "caption_text": sample.discrimination.text,
                "caption_box_decisions": [
                    _caption_box_decision_to_dict(decision)
                    for decision in sample.discrimination.decisions
                ],
            }
            for sample in samples
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


def _caption_box_decision_to_dict(decision: CaptionBoxDecision) -> dict:
    return {
        "text": decision.text,
        "confidence": decision.confidence,
        "bbox": list(decision.bbox),
        "score": decision.score,
        "kept": decision.kept,
        "reasons": list(decision.reasons),
    }


def _scan_times(start_t: float, end_t: float, step: float) -> list[float]:
    times: list[float] = []
    index = 0
    while True:
        t = start_t + index * step
        if t >= end_t:
            return times
        times.append(t)
        index += 1


def _scan_frames(
    source: FrameSource,
    start_t: float,
    end_t: float,
    fps: float,
) -> Iterator[tuple[float, Image.Image]]:
    if hasattr(source, "frames"):
        yield from source.frames(fps, start_t, end_t - start_t)
        return
    for t in _scan_times(start_t, end_t, 1.0 / fps):
        yield t, source.frame_at(t)


def _scan_end_t(video: Path, config: SubConfig) -> float:
    if config.scan_duration is not None:
        return config.scan_start + config.scan_duration
    return _video_duration(video)


def _video_duration(video: Path) -> float:
    raw = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video),
        ],
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return float(raw.strip())


def _build_recognizer(config: SubConfig) -> TextRecognizer:
    if config.ocr_engine == "vision" or (
        config.ocr_engine == "auto" and _vision_is_available()
    ):
        return VisionRecognizer(config.frame.ocr_lang)
    return TesseractRecognizer(config.frame.ocr_lang, config.frame.ocr_psm)


def _vision_is_available() -> bool:
    return sys.platform == "darwin" and importlib.util.find_spec("ocrmac") is not None


def _resolve_text_script(config: SubConfig) -> TextScript:
    if config.text_script != "auto":
        return config.text_script
    lang_parts = {
        part.strip().casefold()
        for separator in ("+", ",")
        for part in config.frame.ocr_lang.replace(separator, "+").split("+")
    }
    if lang_parts & {"ja", "jpn", "japanese"}:
        return "japanese"
    return "none"
