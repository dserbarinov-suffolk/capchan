# Capchan — Design Document

**Status:** Finalized for implementation
**Scope:** Architecture and module decomposition for the Capchan monorepo and its two tools, `deckchan` and `subchan`.
**Audience:** Maintainers and AI coding agents working in the repository.

This document defines *what* Capchan is and *how* its parts divide responsibility. It contains no implementation code. It records the design that the implementation must follow.

---

## 1. Purpose

Capchan extracts text-bearing content that is burned into video pixels. It serves two tasks:

- **`deckchan`** turns a slide-style video — static slides held while someone narrates — into a slide deck.
- **`subchan`** turns a video with burned-in subtitles into a subtitle file.

Both tasks rest on one observation: the wanted content is a region of text that **holds still** for a span of time, then changes. Capchan finds those held spans, reads them, and groups them. The two tools differ only in how they group the spans and what they write out.

The target platform is an Apple Silicon Mac (M5). The design isolates that choice (§4.3, §6, §11), so support for another platform is a new adapter, not a rewrite.

---

## 2. Glossary

This project uses one term per concept. Each term below has exactly one meaning. Do not substitute synonyms in code or documentation.

| Term | Meaning |
|---|---|
| frame | One decoded image from the video at a single timestamp. |
| sample | A frame taken at the sampling rate. The pipeline reads samples, not every frame. |
| difference series | The sequence of mean-absolute-difference values between consecutive samples. |
| threshold | The difference value that separates a static sample from a moving sample. |
| stationarity gate | The step that labels each sample static or moving, and groups static samples into segments. |
| segment | A maximal run of consecutive static samples. One segment is one held span of still content. |
| representative frame | The single full-resolution frame chosen to stand for a segment. It is the last held frame of the segment. |
| recognized text | The lines a recognizer reads from one frame. Each line has text, a confidence, and a box. |
| token set | The set of normalized text tokens recognized in a segment. |
| text identity | The relation between two token sets: equal, subset, or different. |
| error budget | The rule that a false positive (an extra item, removed by hand) costs less than a false negative (lost content). |
| slide | One output page of `deckchan`. A slide is a run of segments merged by equal-or-subset text identity. |
| build | A slide whose text grows across consecutive segments. The segments form a subset chain. |
| hardsub | A subtitle burned into the video pixels. A hardsub is not a separate track. |
| caption | One piece of on-screen hardsub text. |
| caption event | One output entry of `subchan`: a start time, an end time, and caption text. |
| trace | The machine-readable record of every decision in one run. The trace exists for diagnosis, separate from the output artifact. |

---

## 3. Scope

### In scope (v1)

- Held-text extraction from a local video file, on Apple Silicon (M5).
- `deckchan`: slide deck output (PDF, optional PPTX).
- `subchan`: subtitle output (SRT, optional VTT) for hardsubs, in two recognition modes (banded and full-frame).
- A shared kernel, `framechan`, that both tools consume.
- A trace per run, for the tuning pass.

### Out of scope (v1)

- Other platforms. Capchan targets M5. A port boundary keeps cross-platform support additive (§11), but it is not a v1 goal.
- Cross-time grouping. A return to an earlier slide, or a repeated caption far apart in time, becomes a separate item (§10, I2).
- Regional stationarity. A slide beside a moving presenter, or a picture-in-picture layout, is not detected. The gate measures the whole frame.
- Subtitle translation, speaker labels, and styled output (ASS).
- Audio transcription. Capchan reads pixels, not sound.

---

## 4. Architecture

### 4.1 Style

Capchan uses Domain-Driven Design with a Hexagonal (ports and adapters) architecture. The pure logic — the gate, text identity, the merges, the discrimination — is the **domain**. Everything that crosses the boundary to the outside world — video decoding, text recognition, file output — enters through a **port** and is realized by an **adapter**. The domain depends on ports, never on adapters.

Architecture vocabulary (one term per concept):

| Term | Meaning |
|---|---|
| domain | The pure business logic and the value objects it acts on. It performs no I/O. |
| port | An interface the core owns. It states *what* the core needs, not *how* it is done. |
| adapter | A concrete implementation of a port. It holds all the technology-specific code. |
| driving (primary) | A caller that drives the core. The CLI is a driving adapter. |
| driven (secondary) | A dependency the core calls out to. ffmpeg, Apple Vision, and the file writers are driven adapters. |
| use case | An application service that wires the domain to its ports to fulfill one task. |

### 4.2 The hexagon

```
       DRIVING SIDE                    CORE  (no I/O)                    DRIVEN SIDE
     primary adapters                                                 secondary adapters

  +----------------+               +--------------------------+
  | deckchan CLI   |--.            |       application        |       FrameSource
  +----------------+  |   drives   |       (use cases)        |--------------------> ffmpeg
                      +----------->|--------------------------|       TextRecognizer
  +----------------+  |            |          DOMAIN          |--------------------> Apple Vision
  | subchan  CLI   |--'            |  difference | gate       |       DeckWriter
  +----------------+               |  text-identity | merge   |--------------------> PDF / PPTX
                                   |  discrimination          |       SubtitleWriter
                                   +--------------------------+--------------------> SRT / VTT

   left ports are driven by the world          right ports are driven by the core
```

### 4.3 The dependency rule

Source dependencies point inward. `domain` imports nothing outside itself. `ports` are interfaces the core owns. `adapters` and CLIs depend on the core through those ports; the core never imports an adapter. **The only Apple-specific code in the whole system is the Apple Vision adapter** (§6, §11). A new platform adds a sibling adapter file and changes nothing else. This rule is invariant I7 (§10).

### 4.4 One kernel, two consumers

`framechan` is the shared kernel. It carries a video to "segments with recognized text" and stops there, task-blind. It owns the difference, gate, and text-identity domain logic, the `FrameSource` and `TextRecognizer` ports, and the adapters for them. `deckchan` and `subchan` depend on `framechan`. They diverge only at the merge step and the output writer. Everything below that line is shared. That is the whole point of the split.

---

## 5. Domain model

### 5.1 Value objects

These types are immutable and pure. They carry no behavior that touches the outside world.

```python
# framechan.domain
@dataclass(frozen=True)
class DifferenceSeries:
    fps: float
    times: tuple[float, ...]      # one entry per sample
    diffs: tuple[float, ...]      # mean abs difference, 0..1; diffs[0] == 0

@dataclass(frozen=True)
class Segment:
    start_t: float
    end_t: float
    representative_t: float       # the last held frame, less a half-sample margin
    n_samples: int
    passed: bool                  # cleared the minimum-duration floor

@dataclass(frozen=True)
class TextBox:
    text: str
    confidence: float
    bbox: tuple[float, float, float, float]   # x, y, w, h, normalized 0..1

@dataclass(frozen=True)
class RecognizedText:
    lines: tuple[TextBox, ...]    # line-level boxes (see §11)
    # .text joins lines in reading order: top-to-bottom, then left-to-right

@dataclass(frozen=True)
class SegmentText:
    segment: Segment
    recognized: RecognizedText
    tokens: frozenset[str]
```

```python
# deckchan.domain
@dataclass(frozen=True)
class Slide:
    index: int
    source_segments: tuple[int, ...]
    occurrences: tuple[tuple[float, float], ...]
    representative_frame: Path
    text: str

# subchan.domain
@dataclass(frozen=True)
class CaptionEvent:
    index: int
    start_t: float
    end_t: float
    text: str
```

### 5.2 Domain services

Each service is pure: same input, same output, no I/O.

- **Difference** (`framechan`) — turns a stream of downscaled grayscale samples into a `DifferenceSeries`. The difference metric lives here, because how change is measured is a domain decision.
- **Gate** (`framechan`) — chooses the threshold from the series' own histogram with Otsu in log space, then groups samples into segments and applies the minimum-duration floor.
- **TextIdentity** (`framechan`) — tokenizes recognized text and measures token-set containment. It reports the relation: equal, subset, or different.
- **SlideMerge** (`deckchan`) — walks segments in time order and merges them into slides by text identity (§8).
- **CaptionDiscrimination** (`subchan`) — scores text boxes across segments and keeps caption-like boxes, then joins them in reading order (§9).
- **EventMerge** (`subchan`) — merges consecutive segments with the same caption text into one timed caption event (§9).

---

## 6. Ports

A port is the information-hiding boundary for one external concern, in the Parnas sense: the interface states the need, the adapter hides the decision that is likely to change. `framechan` owns the two shared ports; each tool owns its writer port.

| Port | Owner | Secret it hides | Interface |
|---|---|---|---|
| `FrameSource` | `framechan` | How a video is decoded, sampled, downscaled, and seeked. | `samples(fps, w, h) -> Iterator[(t, gray)]`; `frame_at(t) -> Image` |
| `TextRecognizer` | `framechan` | Which engine recognizes text, and how. | `recognize(image) -> RecognizedText` |
| `DeckWriter` | `deckchan` | The output document format. | `write(slides, path) -> None` |
| `SubtitleWriter` | `subchan` | The subtitle file format. | `write(events, path) -> None` |

```python
# framechan.ports
class FrameSource(Protocol):
    def samples(self, fps: float, width: int, height: int) -> Iterator[tuple[float, "NDArray"]]:
        """Yield (timestamp, downscaled grayscale frame) across the whole video."""
    def frame_at(self, t: float) -> "Image":
        """Return one full-resolution frame at time t."""

class TextRecognizer(Protocol):
    def recognize(self, image: "Image") -> RecognizedText:
        """Return recognized lines, each with text, confidence, and a bounding box."""
```

---

## 7. Adapters

An adapter holds all the technology-specific code for one port. Adapters depend on the core; the core does not depend on them.

| Adapter | Port | Notes |
|---|---|---|
| `FfmpegFrameSource` | `FrameSource` | Decodes via an ffmpeg pipe. Yields downscaled grayscale samples for the difference pass; seeks for full-resolution representative frames. |
| `VisionRecognizer` | `TextRecognizer` | Apple Vision via `ocrmac` / `pyobjc`. On-device, runs on the Neural Engine, returns line-level boxes. **The single Apple-specific module.** |
| `FakeRecognizer` | `TextRecognizer` | A deterministic test double. Lets the domain and use cases run in CI without a Mac or Vision. |
| `PdfDeckWriter` | `DeckWriter` | One full-resolution frame per page, via Pillow. |
| `PptxDeckWriter` | `DeckWriter` | One image per slide, via `python-pptx`. |
| `SrtSubtitleWriter` | `SubtitleWriter` | SRT timecodes and text. |
| `VttSubtitleWriter` | `SubtitleWriter` | WebVTT. |

The trace is written by a small JSON writer in the application layer; it is diagnostics, not a domain concern.

---

## 8. `deckchan`

`deckchan` adds one domain service and one writer port to the shared kernel.

**Merge rule (`SlideMerge`).** Walk the segments in time order. Compare each segment only to the slide under construction. Apply text identity:

- equal token sets → the same slide. Merge.
- the current text is a subset of the new segment → a build. Merge, and keep the larger frame.
- either side has too few tokens → keep both. Do not trust the comparison.
- otherwise → a new slide.

The representative frame of a slide is the member segment with the most tokens. For a build, that is the last step, which contains all earlier content.

**Use case (`ExtractDeck`).** Get segments from `framechan`. Run `SlideMerge`. Hand the slides to a `DeckWriter`. Write the trace and a difference plot.

`deckchan` is the former `slidewalk` tool. The refactor moves sampling, gate, recognition, and the text primitives into `framechan`, and leaves only the slide rule and the deck writers in `deckchan`.

---

## 9. `subchan`

`subchan` adds three domain services and one writer port.

**Recognition mode.** A hardsub can sit in a fixed band or float anywhere.

- *banded* — recognize a fixed region, for example the lower third. Fast. Use it when the caption position is fixed.
- *full-frame* — recognize the whole frame. Use it when the caption floats. Slower, and it also sees other on-screen text.

The band crop and a brightness pre-pass (which blackens pixels below a brightness threshold, so a light caption with a dark outline stands out) run before recognition. Both are backend-independent input conditioning, applied to the image before it reaches the `TextRecognizer` port — a direct benefit of the port boundary.

**Discrimination (`CaptionDiscrimination`).** In full-frame mode other text competes with the caption: titles, credits, signage, interface labels. `subchan` scores each text box and keeps the caption-like ones. The signals, in order of weight:

1. *Persistence (primary).* A caption stays for one to several seconds, then leaves. A logo stays for the whole video. A title is welded to a hard cut. This signal is free: it reuses the segment timing `framechan` already computed.
2. *Contrast.* A caption is high-contrast text, often with an outline or a box. This fits emphasis floats well — they are short, large, and high-contrast.
3. *Size band.* Caption text sits in a height range. Very large or very small text is not a caption.
4. *Position (soft).* A caption sits in a stable zone. For floating text this signal is weak by definition, so it is a tie-breaker, not a gate.

When a box is ambiguous, keep it (invariant I2) and record the score in the trace, so a wrong call is a prune, not a lost line — `subchan` does not aim to classify perfectly. Within a segment, join all kept boxes in reading order (top-to-bottom, then left-to-right) into one caption, so a lower-third line and a simultaneous floating emphasis word land in one coherent caption.

**Merge and output (`EventMerge`).** Merge consecutive segments whose caption text is the same, within OCR tolerance, into one caption event. Set the event start and end from the segment times. Hand the events to a `SubtitleWriter`. Write the trace.

`subchan` v1 ships the banded mode, and the full-frame mode with persistence, contrast, and size, with position as a soft tie-breaker. Learned position or color models for arbitrary floating captions are later work (§3, §14).

---

## 10. Invariants

These rules hold across the whole monorepo. A change that breaks one of these rules is a design change, not a fix.

- **I1 — No per-video magic numbers.** Every parameter is in an invariant unit: the video's own statistics (the auto threshold), a semantic duration (the minimum on-screen time), or an OCR-noise-scale tolerance. A bespoke constant fitted to one video is not allowed.
- **I2 — One-directional error budget.** Bias toward over-capture. A false positive is one item to delete. A false negative is lost content. When in doubt, keep the item.
- **I3 — Compare only adjacent segments.** Walk segments in time order. Compare each segment to its immediate predecessor in that order. Never bridge a gap by guesswork. Global grouping is out of scope.
- **I4 — Represent a segment by its last held frame.** A built-up slide, or a late-corrected caption, then comes out complete.
- **I5 — `framechan` is task-blind.** `framechan` knows nothing about slides or captions. `deckchan` and `subchan` know nothing about each other.
- **I6 — Every run emits a trace.** The output artifact is not enough. Each run records its difference series, its segments, the recognized text, and every merge decision, so a missing item is a glance, not a debugging session.
- **I7 — Dependencies point inward.** `domain` imports nothing outside itself. Adapters depend on the core through ports; the core never imports an adapter. The only platform-specific code is the OCR adapter.

---

## 11. The `TextRecognizer` port and the Apple Vision adapter

OCR is the flagship of the hexagonal design. The core depends only on the `TextRecognizer` port. The production adapter is Apple Vision.

- **`VisionRecognizer` (production).** Apple Vision via `ocrmac` / `pyobjc`. It is on-device, runs on the Neural Engine, and returns each line with text, confidence, and a bounding box. It is private and fast on Apple Silicon.
- **`FakeRecognizer` (tests).** A deterministic double. The domain and the use cases are testable in CI with no Mac and no Vision — a direct payoff of the port boundary.
- **Future adapters.** Tesseract, EasyOCR, or the PaddleOCR-VL MLX build can each become an adapter behind the same port if another platform or a stronger model is needed. (Classic PaddleOCR is unreliable on Apple Silicon and is not a candidate for the default.)

**The `boxes()` contract is line-level.** Each adapter normalizes its output to one box per line. Apple Vision returns line observations natively. A future word-level engine groups its word boxes into lines. This keeps `CaptionDiscrimination` reasoning over lines, independent of the engine.

---

## 12. Repository layout

Capchan is a `uv` workspace. Each package is installable on its own. `framechan` is a workspace path-dependency of the two tools. Each package is laid out by layer: `domain`, `ports`, `adapters`, `application`.

```
Capchan/
  pyproject.toml                      # uv workspace root; members = packages/*
  uv.lock
  README.md
  docs/
    design.md                         # this document
  packages/
    framechan/                        # shared kernel: video -> segments with text
      pyproject.toml
      src/framechan/
        domain/
          difference.py               # DifferenceSeries + difference metric
          segment.py                  # Segment value object
          gate.py                     # threshold (log-Otsu) + find_segments
          text.py                     # TextBox, RecognizedText, tokenize, containment, identity
        ports/
          frame_source.py             # FrameSource protocol
          text_recognizer.py          # TextRecognizer protocol
        adapters/
          ffmpeg_frame_source.py      # ffmpeg adapter
          vision_recognizer.py        # Apple Vision adapter  <-- ONLY Apple-specific file
          fake_recognizer.py          # deterministic test double
        application/
          extract_segments.py         # shared pipeline use case (wires the ports)
        trace.py                      # trace record + JSON writer
        config.py                     # sampling / gate / text tolerances
    deckchan/                         # tool: slides
      pyproject.toml                  # depends on framechan
      src/deckchan/
        domain/
          slide.py                    # Slide + SlideMerge (equal / subset)
        ports/
          deck_writer.py              # DeckWriter protocol
        adapters/
          pdf_deck_writer.py          # Pillow image-PDF
          pptx_deck_writer.py         # python-pptx
        application/
          extract_deck.py             # ExtractDeck use case
        cli.py                        # driving adapter
        config.py
    subchan/                          # tool: subtitles
      pyproject.toml                  # depends on framechan
      src/subchan/
        domain/
          caption.py                  # CaptionEvent
          discriminate.py             # CaptionDiscrimination (persistence/contrast/size; box-join)
          events.py                   # EventMerge (same-text -> timed event)
        ports/
          subtitle_writer.py          # SubtitleWriter protocol
        adapters/
          srt_writer.py
          vtt_writer.py
        application/
          extract_subtitles.py        # ExtractSubtitles use case (banded / full-frame; brightness pre-pass)
        cli.py                        # driving adapter
        config.py
```

---

## 13. Decisions (resolved)

| # | Decision | Resolution |
|---|---|---|
| 1 | Shared-core name | `framechan`. |
| 2 | Workspace tooling | `uv` workspace. Capchan is a standalone repo, unrelated to `suffolkdesign-mono`. |
| 3 | `subchan` v1 discrimination | Banded + full-frame. Discrimination = persistence (primary) + contrast + size; position soft. Ambiguous boxes are kept, traced, and pruned by hand. Boxes joined per segment in reading order. Learned floating-position models deferred. |
| 4 | Platform and structure | Target M5 only. Encapsulate with DDD. Apply Hexagonal architecture: OCR (and, for consistency, video decoding and output) sit behind ports; Apple Vision is one adapter. A new platform is a new adapter, not a redesign. |

---

## 14. Future work

- Cross-time grouping, to fold a repeated slide or caption into one item.
- Regional stationarity, for picture-in-picture and presenter-beside-slide layouts.
- Additional `TextRecognizer` adapters (Tesseract, EasyOCR, PaddleOCR-VL MLX) for other platforms or stronger models.
- `subchan` styled output (ASS), learned floating-position models, and color models.
