"""All tunables live here, deliberately.

Every parameter is expressed in units intrinsic to the *video's own statistics*
or to the *genre* — never to one specific clip. There is no magic pixel constant
fitted to a single video and no "ignore this region at this timestamp" hack.

  - sampling rate / diff resolution : properties of "slides are held for seconds"
  - static_threshold = "auto"        : derived from THIS video's difference histogram (Otsu)
  - min_slide_seconds                : a semantic claim about what a slide is
  - text_overlap / min_text_tokens   : OCR-noise-scale, stable across decks
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Union


@dataclass
class Config:
    # --- sampling -----------------------------------------------------------
    # Slides sit still for seconds, so we do not need sub-half-second resolution
    # to find them. Sampling here also kills frame-by-frame compression noise.
    sample_fps: float = 2.0
    # Downscaled size used ONLY to compute the difference signal. Full-resolution
    # frames are extracted separately for OCR and for the final deck.
    diff_width: int = 96
    diff_height: int = 54

    # --- stationarity gate (slide-vs-not) -----------------------------------
    # "auto"  -> Otsu threshold, computed per-video from its difference histogram.
    # a float -> an absolute mean-abs-difference cutoff in [0, 1]. Use this only
    #            during the tuning pass, when you are calibrating against a real run.
    static_threshold: Union[str, float] = "auto"
    # A real slide is held on screen at least this long. Anything briefer (a
    # one-second B-roll cutaway, a talking head pausing for a beat) is gated out.
    min_slide_seconds: float = 2.0

    # --- text identity (which-slide, and build-vs-new) ----------------------
    # Two frames are the same slide iff their OCR token sets agree to this degree.
    # OCR noise is small and character-level; a slide change is wholesale — so a
    # token-containment cutoff around 0.85 is a property of OCR, not of one video.
    text_overlap: float = 0.85
    # Below this many tokens a segment is "low-text" (a photo, a chart, a title
    # card). Low-text segments are never text-merged and are always kept: the
    # error budget is one-directional, so when in doubt we capture.
    min_text_tokens: int = 3

    # --- ocr ----------------------------------------------------------------
    ocr_lang: str = "eng"
    ocr_psm: int = 6  # treat the frame as a single uniform block of text

    def to_dict(self) -> dict:
        return asdict(self)
