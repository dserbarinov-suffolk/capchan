from __future__ import annotations

from pathlib import Path
from typing import Protocol

from subchan.domain.caption import CaptionEvent


class SubtitleWriter(Protocol):
    def write(self, events: list[CaptionEvent], path: Path) -> None:
        """Write caption events to path."""
