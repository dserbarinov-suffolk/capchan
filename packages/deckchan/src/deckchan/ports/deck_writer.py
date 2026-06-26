from __future__ import annotations

from pathlib import Path
from typing import Protocol

from deckchan.domain.slide import Slide


class DeckWriter(Protocol):
    def write(self, slides: list[Slide], path: Path) -> None:
        """Write slides to path."""
