"""
Service layer untuk Leveling System (Stage 4).

Menangani semua logic inti: pemberian XP text & voice (dengan anti-spam
cooldown dan daily limit), perhitungan level, rank, leaderboard, prestige,
dan role reward.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone

from bot.database.connection import Database
from bot.models.leveling import LevelConfig, UserLevel
from bot.utils.xp_curve import level_from_xp

CONFIG_EDITABLE_FIELDS = {
    "enabled",
    "xp_per_message_min",
    "xp_per_message_max",
    "xp_cooldown_seconds",
    "daily_xp_limit",
    "voice_xp_enabled",
    "voice_xp_per_minute",
    "voice_xp_min_members",
    "level_up_message_enabled",
    "level_up_channel_id",
    "level_up_message",
    "level_up_use_card",
    "prestige_enabled",
    "prestige_required_level",
    "rank_card_background",
    "leaderboard_background",
}


@dataclass
class XpAwardResult:
    awarded: bool
    xp_gained: int
    old_level: int
    new_level: int
    leveled_up: bool


class LevelingService:
    def __init__(self, db: Database):
        self.db = db
        self._config_cache: dict[int, LevelConfig] = {}

    # ================= CONFIG =================

    async def get_config(self, guild_id: int) -> LevelConfig:
        if guild_id in self._config_cache:
            return self._config_cache[guild_id]

        row = await self.db.fetchone(
            "SELECT * FROM level_config WHERE guild_id = ?", (str(guild_id),)
        )
        if row is None:
            await self.db.execute(
                "INSERT INTO level_config (guild_id) VALUES (?)", (str(guild_id),)
            )
            row = await self.db.fetchone(
                "SELECT * FROM level_config WHERE guild_id = ?", (str(guild_id),)
            )

        cfg = LevelConfig.from_row(row)
        self._config_cache[guild_id] = cfg
        return cfg

    async def set_config_field(self, guild_id: int, column: str, value) -> None:
        if column not in CONFIG_EDITABLE_FIELDS:
            raise ValueError(f"Kolom '{column}' tidak diizinkan diubah.")
        await self.get_config(guild_id)  # pastikan row ada
        await self.db.execute(
            f"UPDATE level_config SET {column} = ?, updated_at = datetime('now') WHERE guild_id = ?",
            (value, str(guild_id)),
        )
        self._config_cache.pop(guild_id, None)

    # ================= USER DATA =================

    async def get_user(self, guild_id: int, user_id: int) -> UserLevel:
        row = await self.db.fetchone(
            "SELECT * FROM user_levels WHERE guild_id = ? AND user_id = ?",
            (str(guild_id), str(user_id)),
        )
        if row is None:
            await self.db.execute(
                "INSERT INTO user_levels (guild_id, user_id) VALUES (?, ?)",
                (str(guild_id), str(user_id)),
            )
            row = await self.db.fetchone(
                "SELECT * FROM user_levels WHERE guild_id = ? AND user_id = ?",
                (str(guild_id), str(user_id)),
            )
        return UserLevel.from_row(row)

    async def _reset_daily_if_needed(self, user: UserLevel) -> UserLevel:
        today = datetime.now(timezone.utc).date().isoformat()
        if user.daily_xp_date != today:
            await self.db.execute(
                "UPDATE user_levels SET daily_xp_earned = 0, daily_xp_date = ? WHERE guild_id = ? AND user_id = ?",
                (today, user.guild_id, user.user_id),
            )
            user.daily_xp_earned = 0
            user.daily_xp_date = today
        return user

    # ================= AWARD XP =================

    async def add_text_xp(self, guild_id: int, user_id: int) -> XpAwardResult:
        config = await self.get_config(guild_id)
        user = await self.get_user(guild_id, user_id)
        user = await self._reset_daily_if_needed(user)

        now = datetime.now(timezone.utc)

        # Anti-spam cooldown
        if user.last_text_xp_at:
            last = datetime.fromisoformat(user.last_text_xp_at)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            elapsed = (now - last).total_seconds()
            if elapsed < config.xp_cooldown_seconds:
                old_level, _, _ = level_from_xp(user.xp)
                return XpAwardResult(False, 0, old_level, old_level, False)

        # Daily limit
        if config.daily_xp_limit > 0 and user.daily_xp_earned >= config.daily_xp_limit:
            old_level, _, _ = level_from_xp(user.xp)
            return XpAwardResult(False, 0, old_level, old_level, False)

        gained = random.randint(config.xp_per_message_min, config.xp_per_message_max)
        old_level, _, _ = level_from_xp(user.xp)
        new_total_xp = user.xp + gained
        new_level, _, _ = level_from_xp(new_total_xp)

        await self.db.execute(
            """
            UPDATE user_levels
            SET xp = ?, total_messages = total_messages + 1,
                last_text_xp_at = ?, daily_xp_earned = daily_xp_earned + ?,
                updated_at = datetime('now')
            WHERE guild_id = ? AND user_id = ?
            """,
            (new_total_xp, now.isoformat(), gained, str(guild_id), str(user_id)),
        )

        return XpAwardResult(True, gained, old_level, new_level, new_level > old_level)

    async def add_voice_xp(self, guild_id: int, user_id: int, minutes: int = 1) -> XpAwardResult:
        config = await self.get_config(guild_id)
        user = await self.get_user(guild_id, user_id)

        gained = config.voice_xp_per_minute * minutes
        old_level, _, _ = level_from_xp(user.xp)
        new_total_xp = user.xp + gained
        new_level, _, _ = level_from_xp(new_total_xp)

        await self.db.execute(
            """
            UPDATE user_levels
            SET xp = ?, voice_minutes = voice_minutes + ?, updated_at = datetime('now')
            WHERE guild_id = ? AND user_id = ?
            """,
            (new_total_xp, minutes, str(guild_id), str(user_id)),
        )

        return XpAwardResult(True, gained, old_level, new_level, new_level > old_level)

    # ================= RANK & LEADERBOARD =================

    async def get_rank(self, guild_id: int, user_id: int) -> int:
        user = await self.get_user(guild_id, user_id)
        row = await self.db.fetchone(
            """
            SELECT COUNT(*) AS cnt FROM user_levels
            WHERE guild_id = ? AND (prestige > ? OR (prestige = ? AND xp > ?))
            """,
            (str(guild_id), user.prestige, user.prestige, user.xp),
        )
        return int(row["cnt"]) + 1

    async def get_leaderboard(self, guild_id: int, limit: int = 10, offset: int = 0) -> list[UserLevel]:
        rows = await self.db.fetchall(
            """
            SELECT * FROM user_levels
            WHERE guild_id = ?
            ORDER BY prestige DESC, xp DESC
            LIMIT ? OFFSET ?
            """,
            (str(guild_id), limit, offset),
        )
        return [UserLevel.from_row(r) for r in rows]

    async def get_total_ranked_users(self, guild_id: int) -> int:
        row = await self.db.fetchone(
            "SELECT COUNT(*) AS cnt FROM user_levels WHERE guild_id = ?", (str(guild_id),)
        )
        return int(row["cnt"])

    # ================= PRESTIGE =================

    async def can_prestige(self, guild_id: int, user_id: int) -> tuple[bool, int, int]:
        config = await self.get_config(guild_id)
        user = await self.get_user(guild_id, user_id)
        level, _, _ = level_from_xp(user.xp)
        return level >= config.prestige_required_level, level, config.prestige_required_level

    async def do_prestige(self, guild_id: int, user_id: int) -> int:
        """Reset xp ke 0, prestige + 1. Return prestige baru."""
        user = await self.get_user(guild_id, user_id)
        new_prestige = user.prestige + 1
        await self.db.execute(
            "UPDATE user_levels SET xp = 0, prestige = ?, updated_at = datetime('now') WHERE guild_id = ? AND user_id = ?",
            (new_prestige, str(guild_id), str(user_id)),
        )
        return new_prestige

    async def reset_user(self, guild_id: int, user_id: int) -> None:
        await self.db.execute(
            "DELETE FROM user_levels WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id))
        )

    # ================= ROLE REWARDS =================

    async def set_level_role_reward(self, guild_id: int, level: int, role_id: int) -> None:
        await self.db.execute(
            """
            INSERT INTO level_role_rewards (guild_id, level, role_id) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, level) DO UPDATE SET role_id = excluded.role_id
            """,
            (str(guild_id), level, str(role_id)),
        )

    async def remove_level_role_reward(self, guild_id: int, level: int) -> None:
        await self.db.execute(
            "DELETE FROM level_role_rewards WHERE guild_id = ? AND level = ?", (str(guild_id), level)
        )

    async def get_level_role_rewards(self, guild_id: int) -> list[tuple[int, str]]:
        rows = await self.db.fetchall(
            "SELECT level, role_id FROM level_role_rewards WHERE guild_id = ? ORDER BY level ASC",
            (str(guild_id),),
        )
        return [(r["level"], r["role_id"]) for r in rows]

    async def get_role_rewards_up_to(self, guild_id: int, level: int) -> list[str]:
        rows = await self.db.fetchall(
            "SELECT role_id FROM level_role_rewards WHERE guild_id = ? AND level <= ?",
            (str(guild_id), level),
        )
        return [r["role_id"] for r in rows]

    async def set_prestige_role_reward(self, guild_id: int, prestige: int, role_id: int) -> None:
        await self.db.execute(
            """
            INSERT INTO prestige_role_rewards (guild_id, prestige, role_id) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, prestige) DO UPDATE SET role_id = excluded.role_id
            """,
            (str(guild_id), prestige, str(role_id)),
        )

    async def remove_prestige_role_reward(self, guild_id: int, prestige: int) -> None:
        await self.db.execute(
            "DELETE FROM prestige_role_rewards WHERE guild_id = ? AND prestige = ?", (str(guild_id), prestige)
        )

    async def get_prestige_role_rewards(self, guild_id: int) -> list[tuple[int, str]]:
        rows = await self.db.fetchall(
            "SELECT prestige, role_id FROM prestige_role_rewards WHERE guild_id = ? ORDER BY prestige ASC",
            (str(guild_id),),
        )
        return [(r["prestige"], r["role_id"]) for r in rows]

    async def get_role_reward_for_prestige(self, guild_id: int, prestige: int) -> str | None:
        row = await self.db.fetchone(
            "SELECT role_id FROM prestige_role_rewards WHERE guild_id = ? AND prestige = ?",
            (str(guild_id), prestige),
        )
        return row["role_id"] if row else None
