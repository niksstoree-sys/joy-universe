"""
Service layer untuk Welcome & Leave config.

Satu class dipakai untuk kedua tabel (welcome_config / leave_config) karena
struktur kolomnya identik — cukup beda nama tabel saat instansiasi.
"""

from __future__ import annotations

from bot.database.connection import Database
from bot.models.greeting import GreetingConfig

# Whitelist kolom yang boleh diupdate lewat command, supaya tidak ada
# kemungkinan SQL injection lewat nama kolom dinamis.
EDITABLE_COLUMNS = {
    "channel_id",
    "content",
    "mention_user",
    "embed_enabled",
    "embed_title",
    "embed_description",
    "embed_color",
    "embed_footer_text",
    "embed_footer_icon",
    "embed_thumbnail",
    "embed_image",
    "embed_author_name",
    "embed_author_icon",
    "embed_timestamp",
    "card_enabled",
    "card_background",
    "card_avatar_position",
    "card_text_position",
    "button_label",
    "button_url",
}


class GreetingService:
    def __init__(self, db: Database, table: str):
        if table not in ("welcome_config", "leave_config"):
            raise ValueError("table harus 'welcome_config' atau 'leave_config'")
        self.db = db
        self.table = table
        self._cache: dict[int, GreetingConfig] = {}

    async def get(self, guild_id: int) -> GreetingConfig:
        if guild_id in self._cache:
            return self._cache[guild_id]

        row = await self.db.fetchone(
            f"SELECT * FROM {self.table} WHERE guild_id = ?", (str(guild_id),)
        )
        if row is None:
            await self.db.execute(
                f"INSERT INTO {self.table} (guild_id) VALUES (?)", (str(guild_id),)
            )
            row = await self.db.fetchone(
                f"SELECT * FROM {self.table} WHERE guild_id = ?", (str(guild_id),)
            )

        cfg = GreetingConfig.from_row(row)
        self._cache[guild_id] = cfg
        return cfg

    async def set_enabled(self, guild_id: int, enabled: bool) -> None:
        await self._ensure_row(guild_id)
        await self.db.execute(
            f"UPDATE {self.table} SET enabled = ?, updated_at = datetime('now') WHERE guild_id = ?",
            (int(enabled), str(guild_id)),
        )
        self._cache.pop(guild_id, None)

    async def set_field(self, guild_id: int, column: str, value) -> None:
        if column not in EDITABLE_COLUMNS:
            raise ValueError(f"Kolom '{column}' tidak diizinkan diubah.")
        await self._ensure_row(guild_id)
        await self.db.execute(
            f"UPDATE {self.table} SET {column} = ?, updated_at = datetime('now') WHERE guild_id = ?",
            (value, str(guild_id)),
        )
        self._cache.pop(guild_id, None)

    async def reset(self, guild_id: int) -> None:
        await self.db.execute(f"DELETE FROM {self.table} WHERE guild_id = ?", (str(guild_id),))
        self._cache.pop(guild_id, None)
        await self._ensure_row(guild_id)

    async def _ensure_row(self, guild_id: int) -> None:
        row = await self.db.fetchone(
            f"SELECT guild_id FROM {self.table} WHERE guild_id = ?", (str(guild_id),)
        )
        if row is None:
            await self.db.execute(
                f"INSERT INTO {self.table} (guild_id) VALUES (?)", (str(guild_id),)
            )

    def invalidate(self, guild_id: int) -> None:
        self._cache.pop(guild_id, None)
