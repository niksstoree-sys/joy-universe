"""Parsing durasi berformat singkat (10s, 5m, 2h, 1d, 1w) untuk command moderasi."""

from __future__ import annotations

import re

DURATION_REGEX = re.compile(r"(\d+)\s*(s|m|h|d|w)", re.IGNORECASE)

UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}

MAX_TIMEOUT_SECONDS = 28 * 86400  # batas maksimal timeout native Discord: 28 hari


def parse_duration(text: str) -> int:
    """
    Parse string durasi seperti '10m', '1h30m', '2d' menjadi total detik.
    Raises ValueError kalau format tidak valid.
    """
    matches = DURATION_REGEX.findall(text.strip().lower())
    if not matches:
        raise ValueError(
            "Format durasi tidak valid. Gunakan contoh: `10m` (10 menit), `1h` (1 jam), `2d` (2 hari), `1h30m`."
        )
    total_seconds = 0
    for amount_str, unit in matches:
        total_seconds += int(amount_str) * UNIT_SECONDS[unit]
    return total_seconds


def format_duration(seconds: int) -> str:
    """Format total detik menjadi string ringkas, misal 3665 -> '1h 1m 5s'."""
    parts = []
    remaining = seconds
    for unit, unit_seconds in (("w", 604800), ("d", 86400), ("h", 3600), ("m", 60), ("s", 1)):
        value, remaining = divmod(remaining, unit_seconds)
        if value > 0:
            parts.append(f"{value}{unit}")
    return " ".join(parts) if parts else "0s"
