from __future__ import annotations

from PIL import Image

from framechan.config import FrameConfig
from framechan.domain.text import RecognizedText, TextBox
from subchan.application.extract_subtitles import extract_subtitles
from subchan.config import SubConfig


class FakeFrameSource:
    def __init__(self) -> None:
        self.frame_times: list[float] = []

    def samples(self, fps: float, width: int, height: int):
        raise AssertionError("scan mode should not use static-diff samples")

    def frame_at(self, t: float) -> Image.Image:
        self.frame_times.append(t)
        return Image.new("RGB", (4, 4), (int(t), 0, 0))


class PixelRecognizer:
    def recognize(self, image: Image.Image) -> RecognizedText:
        text_by_time = {
            1: "hello",
            2: "hello",
        }
        text = text_by_time.get(image.getpixel((0, 0))[0], "")
        lines = (TextBox(text, 1.0, (0.2, 0.5, 0.4, 0.1)),) if text else ()
        return RecognizedText(lines)


def test_scan_mode_ocr_samples_frames_without_static_gate(tmp_path) -> None:
    source = FakeFrameSource()
    config = SubConfig(
        capture_mode="scan",
        frame=FrameConfig(sample_fps=1.0),
        mode="full-frame",
        conditioning="none",
        text_script="none",
        scan_start=0.0,
        scan_duration=3.0,
    )

    result = extract_subtitles(
        "video.mp4",
        tmp_path,
        config,
        frame_source=source,
        recognizer=PixelRecognizer(),
    )

    assert source.frame_times == [0.0, 1.0, 2.0]
    assert result.capture_mode == "scan"
    assert result.n_segments_total == 3
    assert result.n_segments_captured == 2
    assert len(result.events) == 1
    assert result.events[0].start_t == 1.0
    assert result.events[0].end_t == 3.0
    assert result.events[0].text == "hello"
    assert "00:00:01,000 --> 00:00:03,000" in result.srt_path.read_text()
