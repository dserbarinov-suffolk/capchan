# Capchan

Capchan is a Python video-processing monorepo for extracting text-bearing
content that is burned into video pixels.

The workspace currently ships two tools:

- `deckchan` turns slide-style videos into slide decks.
- `subchan` turns videos with burned-in subtitles into subtitle files.

Both tools share `framechan`, the task-blind kernel that samples video frames,
builds a difference series, finds static segments, and recognizes text through a
port.

## License

Capchan is licensed under the PolyForm Noncommercial License 1.0.0.

You may use Capchan for personal, educational, research, or other non-commercial
purposes. Commercial use is not permitted under this license. Commercial users
must obtain a separate commercial license before using Capchan in any business,
product, service, workflow, or revenue-generating activity.

See [LICENSE](./LICENSE) for the full license terms.

## Repository Layout

```text
packages/
  framechan/   shared kernel: video -> segments with recognized text
  deckchan/    slide deck extraction
  subchan/     hardsub subtitle extraction
raw/           ignored source videos; .gitkeep is tracked
out/           ignored generated outputs; .gitkeep is tracked
tests/         focused unit tests for the package contracts
```

## Local Tooling

Use `uv`. Do not assume a system Python workflow on this machine.
`~/.local/bin` is first on `PATH`, `uv` lives there, and there is intentionally
no bare `python` command.

```bash
uv sync --all-packages --dev
uv run pytest
```

Optional OCR engines are installed through extras, not global Python packages:

```bash
uv sync --all-packages --dev --extra vision   # macOS Apple Vision via ocrmac
```

Native media/OCR tools are installed in the local non-root pattern documented at
`~/.local/share/local-tools/README.md`.

Expected commands:

```bash
which ffmpeg      # ~/.local/bin/ffmpeg
which ffprobe     # ~/.local/bin/ffprobe
which tesseract   # ~/.local/bin/tesseract
```

If `uv` fails under an agent sandbox, it may need access to `~/.cache/uv`; rerun
with the appropriate sandbox escalation rather than falling back to system
Python or installing globally.

## deckchan

```bash
uv run deckchan raw/d-Ods9daQPw.mp4 -o out/deckchan-d-Ods9daQPw --pptx
```

Outputs:

```text
out/deckchan-d-Ods9daQPw/
  deck.pdf
  deck.pptx
  diff_series.png
  trace.json
  frames/
```

Useful tuning flags:

```bash
uv run deckchan video.mp4 --fps 2 --min-seconds 2 --text-overlap 0.85
uv run deckchan video.mp4 --ocr-lang eng --ocr-psm 6
```

## subchan

```bash
uv run subchan raw/1eWb6lyi3cU.mp4 -o out/subchan-1eWb6lyi3cU --vtt --ocr-lang jpn
```

Outputs:

```text
out/subchan-1eWb6lyi3cU/
  captions.srt
  captions.vtt
  trace.json
```

`subchan` supports two caption-region modes:

- `banded` recognizes a lower video band after brightness conditioning.
- `full-frame` recognizes the whole frame and applies caption discrimination.

For road-trip or street footage where signs and storefronts create false OCR
hits, use `--bottom-third` to crop OCR to the lower third of the frame before
recognition:

```bash
uv run --extra vision subchan raw/road-trip.mp4 -o out/road-trip --vtt \
  --ocr-lang jpn --bottom-third
```

By default `subchan` finds static scenes first, then OCRs representative frames.
For fast subtitle changes, use `--scan` to OCR fixed-rate samples and merge
adjacent matching text. Use `--start` and `--duration` to test a window before
running a long video, and raise `--fps` for short captions. `--min-confidence`
can drop weak sign/background detections while keeping stronger subtitle text.

```bash
uv run --extra vision subchan raw/1eWb6lyi3cU.mp4 \
  -o out/subchan-1eWb6lyi3cU-scan-10-20 --vtt \
  --ocr-lang jpn --scan --start 10 --duration 11 --fps 2 \
  --mode banded --band-top 0.3 --band-bottom 1 \
  --conditioning none --min-confidence 0.4
```

When `--ocr-lang jpn` is used, `--text-script auto` also requires Japanese text
and trims obvious Latin sign text around Japanese phrases. Use
`--text-script none` to keep every OCR line.

The default recognizer setting is `--ocr-engine auto`. On macOS with the
`vision` extra installed it uses Apple Vision; otherwise it falls back to
Tesseract. For Japanese hardsubs, pass `--ocr-lang jpn`; for English, the
default `eng` is fine.

Recognizer engine options:

- `--ocr-engine auto` is the normal path. It uses Vision on this machine when
  the `vision` extra is present and otherwise uses Tesseract.
- `--ocr-engine vision` forces Apple Vision through the optional `vision` extra
  on macOS. It produced the cleanest full-video result for
  `raw/1eWb6lyi3cU.mp4` in local testing.
- `--ocr-engine tesseract` forces the portable fallback. For the Japanese test video,
  `--conditioning subtitle-outline --band-top 0.74 --ocr-psm 6` works better
  than the plain brightness profile, but spacing/noise is still visible.

Known-good local commands:

```bash
uv run --extra vision subchan raw/1eWb6lyi3cU.mp4 \
  -o out/subchan-1eWb6lyi3cU-vision --vtt \
  --ocr-lang jpn --band-top 0.74

uv run --extra vision subchan raw/1eWb6lyi3cU.mp4 \
  -o out/subchan-1eWb6lyi3cU-scan-10-20 --vtt \
  --ocr-lang jpn --scan --start 10 --duration 11 --fps 2 \
  --mode banded --band-top 0.3 --band-bottom 1 \
  --conditioning none --min-confidence 0.4
```

## Design

The architecture is specified in
[docs/2026-06-26-capchan-as-multitool.md](./docs/2026-06-26-capchan-as-multitool.md).

The key invariant is the dependency rule: source dependencies point inward.
Domain modules are pure, ports are owned by the core, and adapters hold the
technology-specific code.
