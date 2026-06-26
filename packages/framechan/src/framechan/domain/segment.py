from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    index: int
    start_t: float
    end_t: float
    representative_t: float
    n_samples: int
    passed: bool

    @property
    def duration(self) -> float:
        return self.end_t - self.start_t
