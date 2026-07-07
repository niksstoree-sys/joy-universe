"""Service layer untuk Auto Moderation System."""

from __future__ import annotations

from bot.database.connection import Database
from bot.models.automod import AutomodConfig

CONFIG_EDITABLE_FIELDS = {
    "enabled",
    "log_channel_id",
    "spam_enabled",
    "spam_message_threshold",
    "spam_interval_seconds",
    "spam_action",
    "spam_timeout_seconds",
    "mention_spam_enabled",
    "mention_spam_threshold",
    "mention_spam_action",
    "mention_spam_timeout_seconds",
    "invite_filter_enabled",
    "invite_filter_action",
    "link_filter_enabled",
    "link_filter_action",
    "caps_filter_enabled",
    "caps_filter_threshold_percent",
    "caps_filter_min_length",
    "caps_filter_action",
    "badword_filter_enabled",
    "badword_action",
    "scam_detection_enabled",
    "scam_detection_action",
    "ghost_ping_enabled",
    "anti_raid_enabled",
    "anti_raid_join_threshold",
    "anti_raid_interval_seconds",
    "anti_raid_action",
    "anti_raid_lockdown_minutes",
}

VALID_ACTIONS = {"delete", "timeout", "kick", "ban"}


class AutomodService:
    def __init__(self, db: Database):
        self.db = db
        self._config_cache: dict[int, AutomodConfig] = {}
        self._badwords_cache: dict[int, list[str]] = {}
        self._whitelist_cache: dict[int, dict[str, set[str]]] = {}

    # ================= CONFIG =================

    async def get_config(self, guild_id: int) -> AutomodConfig:
        if guild_id in self._config_cache:
            return self._config_cache[guild_id]

        row = await self.db.fetchone(
            "SELECT * FROM automod_config WHERE guild_id = ?", (str(guild_id),)
        )
        if row is None:
            await self.db.execute(
                "INSERT INTO automod_config (guild_id) VALUES (?)", (str(guild_id),)
            )
            row = await self.db.fetchone(
                "SELECT * FROM automod_config WHERE guild_id = ?", (str(guild_id),)
            )

        config = AutomodConfig.from_row(row)
        self._config_cache[guild_id] = config
        return config

    async def set_config_field(self, guild_id: int, column: str, value) -> None:
        if column not in CONFIG_EDITABLE_FIELDS:
            raise ValueError(f"Kolom '{column}' tidak diizinkan diubah.")
        await self.get_config(guild_id)
        await self.db.execute(
            f"UPDATE automod_config SET {column} = ?, updated_at = datetime('now') WHERE guild_id = ?",
            (value, str(guild_id)),
        )
        self._config_cache.pop(guild_id, None)

    # ================= WHITELIST =================

    async def get_whitelist(self, guild_id: int) -> dict[str, set[str]]:
        if guild_id in self._whitelist_cache:
            return self._whitelist_cache[guild_id]

        rows = await self.db.fetchall(
            "SELECT target_type, target_id FROM automod_whitelist WHERE guild_id = ?", (str(guild_id),)
        )
        result: dict[str, set[str]] = {"user": set(), "role": set(), "channel": set()}
        for row in rows:
            result.setdefault(row["target_type"], set()).add(row["target_id"])

        self._whitelist_cache[guild_id] = result
        return result

    async def add_to_whitelist(self, guild_id: int, target_type: str, target_id: int) -> None:
        await self.db.execute(
            "INSERT OR IGNORE INTO automod_whitelist (guild_id, target_type, target_id) VALUES (?, ?, ?)",
            (str(guild_id), target_type, str(target_id)),
        )
        self._whitelist_cache.pop(guild_id, None)

    async def remove_from_whitelist(self, guild_id: int, target_type: str, target_id: int) -> None:
        await self.db.execute(
            "DELETE FROM automod_whitelist WHERE guild_id = ? AND target_type = ? AND target_id = ?",
            (str(guild_id), target_type, str(target_id)),
        )
        self._whitelist_cache.pop(guild_id, None)

    # ================= BADWORDS =================

    async def get_badwords(self, guild_id: int) -> list[str]:
        if guild_id in self._badwords_cache:
            return self._badwords_cache[guild_id]

        rows = await self.db.fetchall(
            "SELECT word FROM automod_badwords WHERE guild_id = ?", (str(guild_id),)
        )
        words = [row["word"] for row in rows]
        self._badwords_cache[guild_id] = words
        return words

    async def add_badword(self, guild_id: int, word: str) -> None:
        await self.db.execute(
            "INSERT OR IGNORE INTO automod_badwords (guild_id, word) VALUES (?, ?)",
            (str(guild_id), word.lower().strip()),
        )
        self._badwords_cache.pop(guild_id, None)

    async def remove_badword(self, guild_id: int, word: str) -> None:
        await self.db.execute(
            "DELETE FROM automod_badwords WHERE guild_id = ? AND word = ?",
            (str(guild_id), word.lower().strip()),
        )
        self._badwords_cache.pop(guild_id, None)

    # ================= VIOLATION LOG =================

    async def log_violation(self, guild_id: int, user_id: int, rule: str, action_taken: str, detail: str = "") -> None:
        await self.db.execute(
            """
            INSERT INTO automod_violations (guild_id, user_id, rule, action_taken, detail)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(guild_id), str(user_id), rule, action_taken, detail),
        )

    async def get_recent_violations(self, guild_id: int, limit: int = 10) -> list:
        return await self.db.fetchall(
            "SELECT * FROM automod_violations WHERE guild_id = ? ORDER BY created_at DESC LIMIT ?",
            (str(guild_id), limit),
        )
