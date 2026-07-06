"""Model data untuk Leveling System."""

from __future__ import annotations

from dataclasses import dataclass

import aiosqlite


@dataclass
class LevelConfig:
    guild_id: str
    enabled: bool

    xp_per_message_min: int
    xp_per_message_max: int
    xp_cooldown_seconds: int
    daily_xp_limit: int

    voice_xp_enabled: bool
    voice_xp_per_minute: int
    voice_xp_min_members: int

    level_up_message_enabled: bool
    level_up_channel_id: str | None
    level_up_message: str | None
    level_up_use_card: bool

    prestige_enabled: bool
    prestige_required_level: int

    rank_card_background: str | None
    leaderboard_background: str | None

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "LevelConfig":
        return cls(
            guild_id=row["guild_id"],
            enabled=bool(row["enabled"]),
            xp_per_message_min=row["xp_per_message_min"],
            xp_per_message_max=row["xp_per_message_max"],
            xp_cooldown_seconds=row["xp_cooldown_seconds"],
            daily_xp_limit=row["daily_xp_limit"],
            voice_xp_enabled=bool(row["voice_xp_enabled"]),
            voice_xp_per_minute=row["voice_xp_per_minute"],
            voice_xp_min_members=row["voice_xp_min_members"],
            level_up_message_enabled=bool(row["level_up_message_enabled"]),
            level_up_channel_id=row["level_up_channel_id"],
            level_up_message=row["level_up_message"],
            level_up_use_card=bool(row["level_up_use_card"]),
            prestige_enabled=bool(row["prestige_enabled"]),
            prestige_required_level=row["prestige_required_level"],
            rank_card_background=row["rank_card_background"],
            leaderboard_background=row["leaderboard_background"],
        )


@dataclass
class UserLevel:
    guild_id: str
    user_id: str
    xp: int
    prestige: int
    total_messages: int
    voice_minutes: int
    last_text_xp_at: str | None
    daily_xp_earned: int
    daily_xp_date: str | None

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "UserLevel":
        return cls(
            guild_id=row["guild_id"],
            user_id=row["user_id"],
            xp=row["xp"],
            prestige=row["prestige"],
            total_messages=row["total_messages"],
            voice_minutes=row["voice_minutes"],
            last_text_xp_at=row["last_text_xp_at"],
            daily_xp_earned=row["daily_xp_earned"],
            daily_xp_date=row["daily_xp_date"],
        )
