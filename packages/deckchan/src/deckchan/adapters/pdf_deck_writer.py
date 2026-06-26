from __future__ import annotations

from pathlib import Path

from PIL import Image

from deckchan.domain.slide import Slide


class PdfDeckWriter:
    def write(self, slides: list[Slide], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        images = [Image.open(slide.representative_frame).convert("RGB") for slide in slides]
        if not images:
            return
        images[0].save(path, "PDF", save_all=True, append_images=images[1:])
        for image in images:
            image.close()
