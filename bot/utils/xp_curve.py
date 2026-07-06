"""
XP curve untuk Leveling System (Stage 4).

Formula: xp_dibutuhkan_level(n) = 5*n^2 + 50*n + 100
(kurva yang sama dipakai banyak bot leveling populer — makin tinggi level,
makin banyak XP yang dibutuhkan, biar progression terasa 'earned').

total_xp_for_level(n) dihitung pakai closed-form (bukan loop) supaya cepat
walau XP user sudah sangat besar. level_from_xp() pakai binary search di
atas closed-form itu.
"""

from __future__ import annotations

MAX_LEVEL_SEARCH = 100_000


def xp_for_next_level(level: int) -> int:
    """XP yang dibutuhkan untuk naik dari `level` ke `level + 1`."""
    return 5 * (level ** 2) + 50 * level + 100


def total_xp_for_level(level: int) -> int:
    """Total XP kumulatif yang dibutuhkan untuk mencapai `level` dari 0."""
    n = level
    if n <= 0:
        return 0
    return (5 * (n - 1) * n * (2 * n - 1)) // 6 + 25 * n * (n - 1) + 100 * n


def level_from_xp(xp: int) -> tuple[int, int, int]:
    """
    Konversi total XP menjadi (level, xp_into_current_level, xp_needed_for_next_level).
    """
    if xp < 0:
        xp = 0

    lo, hi = 0, MAX_LEVEL_SEARCH
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if total_xp_for_level(mid) <= xp:
            lo = mid
        else:
            hi = mid - 1

    level = lo
    xp_into_level = xp - total_xp_for_level(level)
    xp_needed = xp_for_next_level(level)
    return level, xp_into_level, xp_needed
