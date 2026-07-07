"""Service layer untuk Moderation System (warnings, mod history, log config)."""

from __future__ import annotations

from bot.database.connection import Database
from bot.models.moderation import ModHistoryEntry, ModLogConfig, Warning

LOG_CONFIG_EDITABLE_FIELDS = {
    "log_join_leave",
    "log_message_delete",
    "log_message_edit",
    "log_role_update",
    "log_nickname",
    "log_moderation_action",
    "log_voice",
    "log_emoji_sticker",
    "log_thread",
    "log_webhook",
}


class ModerationService:
    def __init__(self, db: Database):
        self.db = db
        self._log_config_cache: dict[int, ModLogConfig] = {}

    # ================= WARNINGS =================

    async def add_warning(self, guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
        await self.db.connection.execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
            (str(guild_id), str(user_id), str(moderator_id), reason),
        )
        await self.db.connection.commit()
        row = await self.db.fetchone("SELECT last_insert_rowid() AS id")
        return int(row["id"])

    async def get_warnings(self, guild_id: int, user_id: int, active_only: bool = True) -> list[Warning]:
        query = "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ?"
        params: tuple = (str(guild_id), str(user_id))
        if active_only:
            query += " AND active = 1"
        query += " ORDER BY created_at DESC"
        rows = await self.db.fetchall(query, params)
        return [Warning.from_row(r) for r in rows]

    async def remove_warning(self, warning_id: int, guild_id: int) -> bool:
        row = await self.db.fetchone(
            "SELECT id FROM warnings WHERE id = ? AND guild_id = ?", (warning_id, str(guild_id))
        )
        if row is None:
            return False
        await self.db.execute("UPDATE warnings SET active = 0 WHERE id = ?", (warning_id,))
        return True

    async def clear_warnings(self, guild_id: int, user_id: int) -> int:
        warnings = await self.get_warnings(guild_id, user_id, active_only=True)
        await self.db.execute(
            "UPDATE warnings SET active = 0 WHERE guild_id = ? AND user_id = ?",
            (str(guild_id), str(user_id)),
        )
        return len(warnings)

    # ================= MOD HISTORY =================

    async def add_history(
        self, guild_id: int, user_id: int, moderator_id: int, action: str,
        reason: str | None = None, duration_seconds: int | None = None,
    ) -> None:
        await self.db.execute(
            """
            INSERT INTO mod_history (guild_id, user_id, moderator_id, action, reason, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(guild_id), str(user_id), str(moderator_id), action, reason, duration_seconds),
        )

    async def get_history(self, guild_id: int, user_id: int, limit: int = 20) -> list[ModHistoryEntry]:
        rows = await self.db.fetchall(
            "SELECT * FROM mod_history WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT ?",
            (str(guild_id), str(user_id), limit),
        )
        return [ModHistoryEntry.from_row(r) for r in rows]

    # ================= LOG CONFIG =================

    async def get_log_config(self, guild_id: int) -> ModLogConfig:
        if guild_id in self._log_config_cache:
            return self._log_config_cache[guild_id]

        row = await self.db.fetchone(
            "SELECT * FROM mod_log_config WHERE guild_id = ?", (str(guild_id),)
        )
        if row is None:
            await self.db.execute(
                "INSERT INTO mod_log_config (guild_id) VALUES (?)", (str(guild_id),)
            )
            row = await self.db.fetchone(
                "SELECT * FROM mod_log_config WHERE guild_id = ?", (str(guild_id),)
            )

        config = ModLogConfig.from_row(row)
        self._log_config_cache[guild_id] = config
        return config

    async def set_log_config_field(self, guild_id: int, column: str, value: bool) -> None:
        if column not in LOG_CONFIG_EDITABLE_FIELDS:
            raise ValueError(f"Kolom '{column}' tidak diizinkan diubah.")
        await self.get_log_config(guild_id)
        await self.db.execute(
            f"UPDATE mod_log_config SET {column} = ? WHERE guild_id = ?",
            (int(value), str(guild_id)),
        )
        self._log_config_cache.pop(guild_id, None)
