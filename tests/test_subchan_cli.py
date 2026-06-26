from __future__ import annotations

import pytest

import subchan.cli as cli


class _DummyResult:
    def print_summary(self) -> None:
        pass


def test_bottom_third_flag_forces_lower_third_crop(monkeypatch) -> None:
    captured = {}

    def fake_extract_subtitles(video, out, config):
        captured["video"] = video
        captured["out"] = out
        captured["config"] = config
        return _DummyResult()

    monkeypatch.setattr(cli, "extract_subtitles", fake_extract_subtitles)

    assert cli.main(["road.mp4", "--mode", "full-frame", "--bottom-third"]) == 0

    config = captured["config"]
    assert config.mode == "banded"
    assert config.band_top == pytest.approx(2.0 / 3.0)
    assert config.band_bottom == 1.0
