"""Generate a synthetic "edited slide-deck" video to exercise capchan.

It deliberately stresses every behaviour the pipeline claims to handle:
  - slides with DIFFERENT templates (no consistent layout to lean on),
  - a three-step progressive build (tests subset-merge),
  - a low-text slide (tests the capture-biased low-text path),
  - animated test-pattern stretches standing in for talking-head / B-roll
    (tests the stationarity gate and the duration floor),
  - a return to slide 1 with other slides in between (tests that v1 leaves it as
    a duplicate rather than wrongly de-duplicating across time).

Run from the repo root:  python examples/make_test_video.py
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1280, 720, 25
FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def _font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        path = os.path.join(FONT_DIR, name)
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def slide(bg, lines, out: Path) -> None:
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)
    y = 150
    for text, size, color in lines:
        draw.text((120, y), text, font=_font(size), fill=color)
        y += int(size * 1.8)
    img.save(out)


def encode_still(png: Path, dur: int, out: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-loop", "1", "-t", str(dur), "-i", str(png), "-r", str(FPS),
         "-pix_fmt", "yuv420p", "-vf", f"scale={W}:{H}",
         "-c:v", "libx264", "-preset", "ultrafast", "-y", "-v", "error", str(out)],
        check=True,
    )


def encode_motion(dur: int, out: Path) -> None:
    # A zooming fractal: the whole frame changes every frame, the realistic
    # signature of B-roll / full-screen footage. (A small moving region on a
    # static background — a wide-shot talking head, picture-in-picture — would
    # not, and is the documented v1 limitation.)
    subprocess.run(
        ["ffmpeg", "-f", "lavfi",
         "-i", f"mandelbrot=size={W}x{H}:rate={FPS}",
         "-t", str(dur),
         "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast",
         "-y", "-v", "error", str(out)],
        check=True,
    )


def main(out_path: str = "examples/test_video.mp4") -> None:
    work = Path(tempfile.mkdtemp(prefix="capchan_demo_"))
    black, white = (20, 20, 20), (245, 245, 245)

    # slide 1 — white template
    slide(white, [("Quarterly Business Review", 64, black),
                  ("Engineering Org   |   FY26", 36, (90, 90, 90))], work / "s1.png")

    # slide 2 — light-gray template, revealed one bullet at a time
    a1 = [("Agenda", 60, (30, 30, 30)), ("Kickoff and goals", 40, (60, 60, 60))]
    a2 = a1 + [("Architecture deep dive", 40, (60, 60, 60))]
    a3 = a2 + [("Launch timeline", 40, (60, 60, 60))]
    slide((230, 230, 232), a1, work / "s2a.png")
    slide((230, 230, 232), a2, work / "s2b.png")
    slide((230, 230, 232), a3, work / "s2c.png")

    # slide 3 — dark navy template
    slide((20, 30, 60), [("Three principles", 56, white),
                         ("Invariants over heuristics", 38, (200, 210, 230)),
                         ("Calibrate against data", 38, (200, 210, 230)),
                         ("Capture, then prune", 38, (200, 210, 230))], work / "s3.png")

    # slide 4 — teal, almost no text (low-text)
    slide((0, 128, 128), [("fig. 1", 30, (0, 100, 100))], work / "s4.png")

    plan = [
        ("still", "s1.png", 6),
        ("motion", None, 4),
        ("still", "s2a.png", 3),
        ("still", "s2b.png", 3),
        ("still", "s2c.png", 4),
        ("motion", None, 5),
        ("still", "s3.png", 6),
        ("still", "s4.png", 5),
        ("motion", None, 3),
        ("still", "s1.png", 4),  # return to slide 1, slides 2-4 in between
    ]

    scenes = []
    for i, (kind, png, dur) in enumerate(plan):
        scene = work / f"scene{i:02d}.mp4"
        if kind == "still":
            encode_still(work / png, dur, scene)
        else:
            encode_motion(dur, scene)
        scenes.append(scene)

    listfile = work / "list.txt"
    listfile.write_text("".join(f"file '{s}'\n" for s in scenes))

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(listfile),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-y", "-v", "error", str(out)],
        check=True,
    )
    print(f"wrote {out}  ({sum(d for _, _, d in plan)}s)")


if __name__ == "__main__":
    main()
