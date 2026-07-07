"""Model data untuk Auto Moderation config."""

from __future__ import annotations

from dataclasses import dataclass

import aiosqlite


@dataclass
class AutomodConfig:
    guild_id: str
    enabled: bool
    log_channel_id: str | None

    spam_enabled: bool
    spam_message_threshold: int
    spam_interval_seconds: int
    spam_action: str
    spam_timeout_seconds: int

    mention_spam_enabled: bool
    mention_spam_threshold: int
    mention_spam_action: str
    mention_spam_timeout_seconds: int

    invite_filter_enabled: bool
    invite_filter_action: str

    link_filter_enabled: bool
    link_filter_action: str

    caps_filter_enabled: bool
    caps_filter_threshold_percent: int
    caps_filter_min_length: int
    caps_filter_action: str

    badword_filter_enabled: bool
    badword_action: str

    scam_detection_enabled: bool
    scam_detection_action: str

    ghost_ping_enabled: bool

    anti_raid_enabled: bool
    anti_raid_join_threshold: int
    anti_raid_interval_seconds: int
    anti_raid_action: str
    anti_raid_lockdown_minutes: int

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "AutomodConfig":
        return cls(
            guild_id=row["guild_id"],
            enabled=bool(row["enabled"]),
            log_channel_id=row["log_channel_id"],
            spam_enabled=bool(row["spam_enabled"]),
            spam_message_threshold=row["spam_message_threshold"],
            spam_interval_seconds=row["spam_interval_seconds"],
            spam_action=row["spam_action"],
            spam_timeout_seconds=row["spam_timeout_seconds"],
            mention_spam_enabled=bool(row["mention_spam_enabled"]),
            mention_spam_threshold=row["mention_spam_threshold"],
            mention_spam_action=row["mention_spam_action"],
            mention_spam_timeout_seconds=row["mention_spam_timeout_seconds"],
            invite_filter_enabled=bool(row["invite_filter_enabled"]),
            invite_filter_action=row["invite_filter_action"],
            link_filter_enabled=bool(row["link_filter_enabled"]),
            link_filter_action=row["link_filter_action"],
            caps_filter_enabled=bool(row["caps_filter_enabled"]),
            caps_filter_threshold_percent=row["caps_filter_threshold_percent"],
            caps_filter_min_length=row["caps_filter_min_length"],
            caps_filter_action=row["caps_filter_action"],
            badword_filter_enabled=bool(row["badword_filter_enabled"]),
            badword_action=row["badword_action"],
            scam_detection_enabled=bool(row["scam_detection_enabled"]),
            scam_detection_action=row["scam_detection_action"],
            ghost_ping_enabled=bool(row["ghost_ping_enabled"]),
            anti_raid_enabled=bool(row["anti_raid_enabled"]),
            anti_raid_join_threshold=row["anti_raid_join_threshold"],
            anti_raid_interval_seconds=row["anti_raid_interval_seconds"],
            anti_raid_action=row["anti_raid_action"],
            anti_raid_lockdown_minutes=row["anti_raid_lockdown_minutes"],
        )
