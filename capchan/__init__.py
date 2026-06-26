"""capchan - turn a slide-deck-style video into a slide deck."""

from .config import Config
from .pipeline import Result, run

__all__ = ["Config", "Result", "run"]
__version__ = "0.1.0"
