from __future__ import annotations

from pathlib import Path

from subchan.adapters.timecode import srt_time
from subchan.domain.caption import CaptionEvent


class SrtSubtitleWriter:
    def write(self, events: list[CaptionEvent], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        chunks = []
        for event in events:
            chunks.append(
                f"{event.index}\n{srt_time(event.start_t)} --> {srt_time(event.end_t)}\n{event.text}\n"
            )
        path.write_text("\n".join(chunks) + ("\n" if chunks else ""))
