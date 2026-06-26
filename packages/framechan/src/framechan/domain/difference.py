from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class DifferenceSeries:
    fps: float
    times: tuple[float, ...]
    diffs: tuple[float, ...]

    @property
    def size(self) -> int:
        return len(self.diffs)


def difference_series_from_samples(
    samples: Iterable[tuple[float, object]], fps: float
) -> DifferenceSeries:
    times: list[float] = []
    diffs: list[float] = []
    previous: Sequence[float] | None = None

    for t, sample in samples:
        frame = tuple(float(value) for value in _flatten(sample))
        times.append(float(t))
        if previous is None:
            diffs.append(0.0)
        else:
            if len(frame) != len(previous):
                raise ValueError("all samples must have the same shape")
            total = sum(abs(a - b) for a, b in zip(frame, previous))
            diffs.append(total / len(frame) / 255.0 if frame else 0.0)
        previous = frame

    if not times:
        raise ValueError("no samples were provided")
    return DifferenceSeries(fps=float(fps), times=tuple(times), diffs=tuple(diffs))


def _flatten(sample: object) -> Iterable[float]:
    if hasattr(sample, "ravel"):
        return sample.ravel()  # type: ignore[no-any-return]
    if isinstance(sample, (bytes, bytearray)):
        return sample
    if isinstance(sample, Iterable):
        return _flatten_iterable(sample)
    raise TypeError(f"sample is not iterable: {type(sample)!r}")


def _flatten_iterable(values: Iterable[object]) -> Iterable[float]:
    for value in values:
        if isinstance(value, (str, bytes, bytearray)):
            yield from value if not isinstance(value, str) else ()
        elif isinstance(value, Iterable):
            yield from _flatten_iterable(value)
        else:
            yield float(value)
