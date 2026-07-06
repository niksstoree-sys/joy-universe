"""
Embed builder untuk JOY UNIVERSE.

Semua embed di seluruh bot HARUS dibuat lewat class ini supaya konsisten:
warna kuning (#FFD54A) sebagai default, layout modern, footer standar,
dan tidak pakai emoji unicode.
"""

from __future__ import annotations

import discord

from bot.core.config import config
from bot.utils.emojis import emoji


class JoyEmbed(discord.Embed):
    """Embed default JOY UNIVERSE dengan tema kuning premium."""

    def __init__(
        self,
        *,
        title: str | None = None,
        description: str | None = None,
        color: int | None = None,
        url: str | None = None,
    ):
        super().__init__(
            title=title,
            description=description,
            color=color if color is not None else config.default_color,
            url=url,
        )
        self.timestamp = discord.utils.utcnow()

    def set_default_footer(self, guild: discord.Guild | None = None) -> "JoyEmbed":
        icon = guild.icon.url if guild and guild.icon else None
        self.set_footer(text="JOY UNIVERSE", icon_url=icon)
        return self

    @classmethod
    def success(cls, description: str, *, title: str | None = None) -> "JoyEmbed":
        return cls(
            title=title or f"{emoji.success} Berhasil",
            description=description,
            color=0x57F287,
        )

    @classmethod
    def error(cls, description: str, *, title: str | None = None) -> "JoyEmbed":
        return cls(
            title=title or f"{emoji.error} Terjadi Kesalahan",
            description=description,
            color=0xED4245,
        )

    @classmethod
    def warning(cls, description: str, *, title: str | None = None) -> "JoyEmbed":
        return cls(
            title=title or f"{emoji.warning} Peringatan",
            description=description,
            color=0xFEE75C,
        )

    @classmethod
    def info(cls, description: str, *, title: str | None = None) -> "JoyEmbed":
        return cls(
            title=title or f"{emoji.info} Info",
            description=description,
            color=config.default_color,
        )
