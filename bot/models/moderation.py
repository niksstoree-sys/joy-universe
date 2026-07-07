"""Model data untuk Moderation System."""

from __future__ import annotations

from dataclasses import dataclass

import aiosqlite


@dataclass
class Warning:
    id: int
    guild_id: str
    user_id: str
    moderator_id: str
    reason: str
    active: bool
    created_at: str

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "Warning":
        return cls(
            id=row["id"],
            guild_id=row["guild_id"],
            user_id=row["user_id"],
            moderator_id=row["moderator_id"],
            reason=row["reason"],
            active=bool(row["active"]),
            created_at=row["created_at"],
        )


@dataclass
class ModHistoryEntry:
    id: int
    guild_id: str
    user_id: str
    moderator_id: str
    action: str
    reason: str | None
    duration_seconds: int | None
    created_at: str

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "ModHistoryEntry":
        return cls(
            id=row["id"],
            guild_id=row["guild_id"],
            user_id=row["user_id"],
            moderator_id=row["moderator_id"],
            action=row["action"],
            reason=row["reason"],
            duration_seconds=row["duration_seconds"],
            created_at=row["created_at"],
        )


@dataclass
class ModLogConfig:
    guild_id: str
    log_join_leave: bool
    log_message_delete: bool
    log_message_edit: bool
    log_role_update: bool
    log_nickname: bool
    log_moderation_action: bool
    log_voice: bool
    log_emoji_sticker: bool
    log_thread: bool
    log_webhook: bool

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "ModLogConfig":
        return cls(
            guild_id=row["guild_id"],
            log_join_leave=bool(row["log_join_leave"]),
            log_message_delete=bool(row["log_message_delete"]),
            log_message_edit=bool(row["log_message_edit"]),
            log_role_update=bool(row["log_role_update"]),
            log_nickname=bool(row["log_nickname"]),
            log_moderation_action=bool(row["log_moderation_action"]),
            log_voice=bool(row["log_voice"]),
            log_emoji_sticker=bool(row["log_emoji_sticker"]),
            log_thread=bool(row["log_thread"]),
            log_webhook=bool(row["log_webhook"]),
        )
