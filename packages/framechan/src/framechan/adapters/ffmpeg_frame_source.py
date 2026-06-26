from __future__ import annotations

import subprocess
from io import BytesIO
from pathlib import Path
from typing import Iterator

import numpy as np
from PIL import Image


class FfmpegFrameSource:
    def __init__(self, video: str | Path) -> None:
        self.video = Path(video)

    def samples(self, fps: float, width: int, height: int) -> Iterator[tuple[float, np.ndarray]]:
        cmd = [
            "ffmpeg",
            "-i",
            str(self.video),
            "-vf",
            f"fps={fps},scale={width}:{height},format=gray",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-v",
            "error",
            "pipe:1",
        ]
        frame_bytes = width * height
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        if proc.stdout is None:
            raise RuntimeError("ffmpeg stdout pipe was not opened")

        index = 0
        while True:
            chunk = proc.stdout.read(frame_bytes)
            if not chunk:
                break
            if len(chunk) != frame_bytes:
                raise RuntimeError(f"ffmpeg emitted a partial frame for {self.video}")
            frame = np.frombuffer(chunk, dtype=np.uint8).reshape(height, width)
            yield (index / fps, frame)
            index += 1

        rc = proc.wait()
        if rc != 0:
            raise subprocess.CalledProcessError(rc, cmd)

    def frame_at(self, t: float) -> Image.Image:
        cmd = [
            "ffmpeg",
            "-ss",
            f"{t:.3f}",
            "-i",
            str(self.video),
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-v",
            "error",
            "pipe:1",
        ]
        raw = subprocess.run(cmd, capture_output=True, check=True).stdout
        if not raw:
            raise RuntimeError(f"ffmpeg decoded no frame at {t:.3f}s from {self.video}")
        with Image.open(BytesIO(raw)) as image:
            return image.convert("RGB")
