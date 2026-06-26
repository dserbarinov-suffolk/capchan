from __future__ import annotations


def srt_time(seconds: float) -> str:
    whole_ms = int(round(seconds * 1000))
    ms = whole_ms % 1000
    total_s = whole_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def vtt_time(seconds: float) -> str:
    return srt_time(seconds).replace(",", ".")
