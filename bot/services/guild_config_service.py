"""
Service layer untuk guild_configs.

Semua akses/logic terkait konfigurasi per-server (prefix, warna embed,
mod log channel, dll) lewat service ini, supaya Cogs tidak langsung
menyentuh SQL mentah.
"""

from __future__ import annotations

from dataclasses import dataclass

from bot.database.connection import Database


@dataclass
class GuildConfig:
    guild_id: str
    prefix: str
    embed_color: str
    mod_log_channel: str | None
    mute_role_id: str | None
    is_premium: bool


class GuildConfigService:
    def __init__(self, db: Database):
        self.db = db
        self._cache: dict[int, GuildConfig] = {}

    async def get(self, guild_id: int) -> GuildConfig:
        if guild_id in self._cache:
            return self._cache[guild_id]

        row = await self.db.fetchone(
            "SELECT * FROM guild_configs WHERE guild_id = ?", (str(guild_id),)
        )

        if row is None:
            await self.db.execute(
                "INSERT INTO guild_configs (guild_id) VALUES (?)", (str(guild_id),)
            )
            row = await self.db.fetchone(
                "SELECT * FROM guild_configs WHERE guild_id = ?", (str(guild_id),)
            )

        cfg = GuildConfig(
            guild_id=row["guild_id"],
            prefix=row["prefix"],
            embed_color=row["embed_color"],
            mod_log_channel=row["mod_log_channel"],
            mute_role_id=row["mute_role_id"],
            is_premium=bool(row["is_premium"]),
        )
        self._cache[guild_id] = cfg
        return cfg

    async def set_prefix(self, guild_id: int, prefix: str) -> None:
        await self.db.execute(
            """
            INSERT INTO guild_configs (guild_id, prefix) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET prefix = excluded.prefix,
                                                 updated_at = datetime('now')
            """,
            (str(guild_id), prefix),
        )
        self._cache.pop(guild_id, None)

    async def set_mod_log_channel(self, guild_id: int, channel_id: int | None) -> None:
        await self.db.execute(
            """
            INSERT INTO guild_configs (guild_id, mod_log_channel) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET mod_log_channel = excluded.mod_log_channel,
                                                 updated_at = datetime('now')
            """,
            (str(guild_id), str(channel_id) if channel_id else None),
        )
        self._cache.pop(guild_id, None)

    async def set_mute_role_id(self, guild_id: int, role_id: int | None) -> None:
        await self.db.execute(
            """
            INSERT INTO guild_configs (guild_id, mute_role_id) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET mute_role_id = excluded.mute_role_id,
                                                 updated_at = datetime('now')
            """,
            (str(guild_id), str(role_id) if role_id else None),
        )
        self._cache.pop(guild_id, None)

    def invalidate(self, guild_id: int) -> None:
        self._cache.pop(guild_id, None)
