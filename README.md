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

`subchan` supports two recognition modes:

- `banded` recognizes a lower video band after brightness conditioning.
- `full-frame` recognizes the whole frame and applies caption discrimination.

The default recognizer adapter is Tesseract. For Japanese hardsubs, pass
`--ocr-lang jpn`; for English, the default `eng` is fine.

## Design

The architecture is specified in
[docs/2026-06-26-capchan-as-multitool.md](./docs/2026-06-26-capchan-as-multitool.md).

The key invariant is the dependency rule: source dependencies point inward.
Domain modules are pure, ports are owned by the core, and adapters hold the
technology-specific code.
