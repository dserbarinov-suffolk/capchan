from __future__ import annotations

from pathlib import Path

from subchan.adapters.timecode import vtt_time
from subchan.domain.caption import CaptionEvent


class VttSubtitleWriter:
    def write(self, events: list[CaptionEvent], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        chunks = ["WEBVTT\n"]
        for event in events:
            chunks.append(f"{vtt_time(event.start_t)} --> {vtt_time(event.end_t)}\n{event.text}\n")
        path.write_text("\n".join(chunks) + ("\n" if chunks else ""))
