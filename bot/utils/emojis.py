"""
Emoji manager untuk JOY UNIVERSE.

Semua emoji yang dipakai bot (di embed, command, notifikasi, dsb) HARUS
lewat modul ini, bukan emoji unicode langsung. Sumbernya file
`bot/configs/emojis.json`, jadi kalau kamu ganti server emoji, tinggal
edit satu file itu tanpa sentuh kode lain.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("joyuniverse.emojis")

_EMOJI_FILE = Path(__file__).resolve().parent.parent / "configs" / "emojis.json"


class EmojiManager:
    _cache: dict[str, str] | None = None

    @classmethod
    def _load(cls) -> dict[str, str]:
        if cls._cache is None:
            with open(_EMOJI_FILE, "r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
            cls._cache = {k: v for k, v in data.items() if not k.startswith("_")}
            logger.info("Emoji config dimuat: %d emoji terdaftar.", len(cls._cache))
        return cls._cache

    @classmethod
    def get(cls, name: str) -> str:
        """
        Ambil emoji custom berdasarkan nama key di emojis.json.
        Kalau key tidak ditemukan, kembalikan string kosong (bukan crash),
        supaya bot tetap jalan walau emoji belum dikonfigurasi.
        """
        emoji = cls._load().get(name)
        if emoji is None:
            logger.warning("Emoji '%s' tidak ditemukan di emojis.json", name)
            return ""
        return emoji

    @classmethod
    def reload(cls) -> None:
        """Reload emoji dari file (dipakai command owner `reload`)."""
        cls._cache = None
        cls._load()


# Shortcut akses cepat: Emoji.success, Emoji.error, dst.
class Emoji:
    def __getattr__(self, name: str) -> str:
        return EmojiManager.get(name)


emoji = Emoji()
