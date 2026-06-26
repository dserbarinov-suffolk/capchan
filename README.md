# Capchan

```text

        ＿人人人人人人＿
        ＞  CAPCHAN!  ＜
        ￣Y^Y^Y^Y^Y￣

              .-^-.
           __/  cap \__
          /  (｡•̀ᴗ-)  \      [REC]
         /|   /|◎|\   |\
        /_|  /_|__|_\  |_\
             ノ    ヽ

```

## License

Capchan is licensed under the PolyForm Noncommercial License 1.0.0.

You may use Capchan for personal, educational, research, or other non-commercial purposes.

Commercial use is not permitted under this license. Commercial users must obtain a separate commercial license before using Capchan in any business, product, service, workflow, or revenue-generating activity.

See [LICENSE](./LICENSE) for the full license terms.

## What Capchan Does

Turn a video that is *basically a slide deck* — static slides held while someone
talks over them — into an actual slide deck, automatically. Out comes a PDF (and
optionally a PPTX) of the slides, plus a JSON trace of every decision the tool
made so you can see exactly why it produced what it did.

## How it works

Two signals, read off the video itself. No per-video configuration, and no magic
constants fitted to one clip — every parameter is in units the video or the genre
gives you.

**1. Stationarity gate — is this a slide at all?**
Sample frames and measure how much each differs from the one before. A slide is a
held still frame: a long run of near-zero differences. A cut or a build is a brief
spike; a talking head or B-roll is sustained motion. The cutoff between "still"
and "moving" is found per-video with [Otsu's method](https://en.wikipedia.org/wiki/Otsu%27s_method)
on the difference histogram. A minimum-duration floor (a real slide is held at
least a couple of seconds) drops momentary stillness and one-second cutaways.

**2. OCR text-identity — which slide, and is it a build or a new one?**
OCR each held segment and reduce it to a set of tokens. Compare each segment only
to its immediate predecessor in the sequence:

| relation | meaning | action |
|---|---|---|
| equal token sets | same slide (held shot, or cut away and back) | merge |
| current ⊆ next | a bullet appeared — progressive build | merge, keep the last/maximal frame |
| either side low-text | a photo / chart / title card | keep both (don't trust a text compare) |
| otherwise | a genuinely new slide | new slide |

The error budget is one-directional: a false positive is one extra slide you
delete (cheap), a false negative is a slide you lost (expensive). So everything
leans toward over-capture.

## Install

This repo is normally run with `uv`, using the user-local toolchain on this
machine:

```bash
uv sync
```

Two system tools are needed alongside the Python deps:

```bash
# This machine keeps non-root tools in ~/.local/bin.
# See ~/.local/share/local-tools/README.md before installing anything.
which ffmpeg   # expected here: ~/.local/bin/ffmpeg
which ffprobe  # expected here: ~/.local/bin/ffprobe

# The default OCR backend also needs tesseract unless you provide another
# OCRBackend implementation.
which tesseract
```

### Local tooling notes for agents

Do not assume a system Python workflow on this machine. `~/.local/bin` is first
on `PATH`, `uv` lives there, and there is intentionally no bare `python`
command. The system `/usr/bin/python3` is the Xcode Command Line Tools Python
and may be too old for this project, so use `uv run ...` for commands that need
Python. Examples:

```bash
uv run python -m capchan --help
uv run capchan talk.mp4
uv run python examples/make_test_video.py
```

If `uv` fails under an agent sandbox, it may be because it needs access to its
cache under `~/.cache/uv`; rerun with the appropriate sandbox escalation rather
than falling back to system Python or installing tools globally.

## Usage

```bash
capchan talk.mp4                           # writes out/deck.pdf + diagnostics
capchan talk.mp4 --pptx                    # also writes out/deck.pptx
uv run python -m capchan talk.mp4          # equivalent, no install needed
```

Output directory:

```
out/
  deck.pdf          one page per slide (full-resolution frames)
  deck.pptx         optional, with --pptx
  diff_series.png   the difference signal with the gate threshold + captured segments
  trace.json        every segment, every merge decision, the full timeline
  frames/           the captured frames
```

The console prints a timeline and a one-line preview of each slide, e.g.

```
timeline: S1[0.0-6.0]  ·  GAP[6.0-10.0]  ·  S2[10.0-20.0]  ·  ...
 slide  1  [0.0-6.0s]   'Quarterly Business Review Engineering Org FY26'
 slide  2  [10.0-20.0s] 'Agenda Kickoff and goals Architecture deep dive Launch...'
```

## Reading the trace (the tuning pass)

When you run this on a real video and a slide is missing, `trace.json` tells you
which of two things happened, and each points at a different dial:

- **It was gated out.** Look at `segments` around where the slide should be. If
  there is no captured segment there, the gate rejected it. Either it read as
  motion (compare its `diff` values in `difference_series` against
  `static_threshold` — lower the gate with `--static-threshold 0.04`) or it was too
  brief (its `duration` is under the floor — lower it with `--min-seconds 1.5`).
  `diff_series.png` shows this at a glance: green spans are captured, grey spans
  are static-but-too-short.
- **It was merged into a neighbour.** Find its segment in `merge_decisions`. A
  `relation` of `equal` or `build` means its text read as identical-to or a
  subset-of the adjacent slide. If that was wrong, tighten with
  `--text-overlap 0.95`.

So a missing slide is a glance, not a debugging session.

## Known limitations (v1)

- **Returns to an earlier slide become duplicates.** If you show slide 4, then
  slides 5–6, then slide 4 again, the second showing is captured as a separate
  slide. De-duplicating across time (against *all* prior slides) is intentionally
  out of scope — text alone over-merges distinct slides that share a title, and
  the duplicate is cheap to delete. Immediate cut-away-and-return *is* collapsed.
- **Composited / picture-in-picture slides are not detected.** A slide shown
  beside a moving presenter never goes still, so the whole-frame gate excludes it.
  Handling that needs regional stationarity and is out of scope for v1.

## Swapping the OCR engine

The OCR backend is a one-method protocol (`ocr.OCRBackend`). The default is
Tesseract for portability. On macOS, Apple's Vision OCR is faster and on-device;
drop it in by implementing the same interface (e.g. via the
[`ocrmac`](https://pypi.org/project/ocrmac/) package) and passing it to
`run(..., ocr_backend=YourBackend())`:

```python
class VisionBackend:
    def text(self, image) -> str:
        ...  # call Vision, return the recognized text
```
