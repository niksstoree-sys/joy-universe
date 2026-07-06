"""
Model data untuk Welcome & Leave config.
Kedua sistem punya struktur identik, jadi pakai satu dataclass yang sama.
"""

from __future__ import annotations

from dataclasses import dataclass

import aiosqlite


@dataclass
class GreetingConfig:
    """Representasi satu baris welcome_config atau leave_config."""

    guild_id: str
    enabled: bool
    channel_id: str | None

    content: str | None
    mention_user: bool

    embed_enabled: bool
    embed_title: str | None
    embed_description: str | None
    embed_color: str | None
    embed_footer_text: str | None
    embed_footer_icon: str | None
    embed_thumbnail: str | None
    embed_image: str | None
    embed_author_name: str | None
    embed_author_icon: str | None
    embed_timestamp: bool

    card_enabled: bool
    card_background: str | None
    card_avatar_position: str
    card_text_position: str

    button_label: str | None
    button_url: str | None

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "GreetingConfig":
        return cls(
            guild_id=row["guild_id"],
            enabled=bool(row["enabled"]),
            channel_id=row["channel_id"],
            content=row["content"],
            mention_user=bool(row["mention_user"]),
            embed_enabled=bool(row["embed_enabled"]),
            embed_title=row["embed_title"],
            embed_description=row["embed_description"],
            embed_color=row["embed_color"],
            embed_footer_text=row["embed_footer_text"],
            embed_footer_icon=row["embed_footer_icon"],
            embed_thumbnail=row["embed_thumbnail"],
            embed_image=row["embed_image"],
            embed_author_name=row["embed_author_name"],
            embed_author_icon=row["embed_author_icon"],
            embed_timestamp=bool(row["embed_timestamp"]),
            card_enabled=bool(row["card_enabled"]),
            card_background=row["card_background"],
            card_avatar_position=row["card_avatar_position"],
            card_text_position=row["card_text_position"],
            button_label=row["button_label"],
            button_url=row["button_url"],
        )
