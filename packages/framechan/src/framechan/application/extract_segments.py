from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

from framechan.adapters.ffmpeg_frame_source import FfmpegFrameSource
from framechan.adapters.tesseract_recognizer import TesseractRecognizer
from framechan.config import FrameConfig
from framechan.domain.difference import DifferenceSeries, difference_series_from_samples
from framechan.domain.gate import auto_threshold, find_segments
from framechan.domain.segment import Segment
from framechan.domain.text import RecognizedText, SegmentText, tokenize
from framechan.ports.frame_source import FrameSource
from framechan.ports.text_recognizer import TextRecognizer


ImageTransform = Callable[[Image.Image], Image.Image]


@dataclass(frozen=True)
class ExtractedSegments:
    video: Path
    series: DifferenceSeries
    threshold: float
    segments: tuple[Segment, ...]
    texts: tuple[SegmentText, ...]

    @property
    def captured_segments(self) -> tuple[Segment, ...]:
        return tuple(segment for segment in self.segments if segment.passed)


def extract_segments(
    video: str | Path,
    config: FrameConfig,
    frame_source: FrameSource | None = None,
    recognizer: TextRecognizer | None = None,
    image_transform: ImageTransform | None = None,
) -> ExtractedSegments:
    video_path = Path(video)
    source = frame_source or FfmpegFrameSource(video_path)
    text_recognizer = recognizer or TesseractRecognizer(config.ocr_lang, config.ocr_psm)

    samples = source.samples(config.sample_fps, config.diff_width, config.diff_height)
    series = difference_series_from_samples(samples, fps=config.sample_fps)
    threshold = (
        auto_threshold(series.diffs[1:])
        if config.static_threshold == "auto"
        else float(config.static_threshold)
    )
    segments = tuple(find_segments(series, threshold, config.min_segment_seconds))

    texts: list[SegmentText] = []
    for segment in segments:
        if not segment.passed:
            continue
        frame = source.frame_at(segment.representative_t)
        image = image_transform(frame) if image_transform else frame
        recognized = text_recognizer.recognize(image)
        texts.append(
            SegmentText(
                segment=segment,
                recognized=recognized,
                tokens=frozenset(tokenize(recognized.text)),
            )
        )

    return ExtractedSegments(
        video=video_path,
        series=series,
        threshold=threshold,
        segments=segments,
        texts=tuple(texts),
    )


def recognized_text_to_dict(recognized: RecognizedText) -> dict:
    return {
        "text": recognized.text,
        "lines": [
            {"text": line.text, "confidence": line.confidence, "bbox": list(line.bbox)}
            for line in recognized.ordered_lines
        ],
    }
