"""Model data untuk satu baris di tabel `events`."""

from __future__ import annotations

from dataclasses import dataclass

import aiosqlite


@dataclass
class EventRecord:
    id: int
    guild_id: str
    name: str
    description: str | None
    channel_id: str
    role_ping_id: str | None

    run_at: str
    timezone: str
    repeat_type: str

    reminder_minutes: int | None
    reminder_sent: bool

    banner_url: str | None
    thumbnail_url: str | None
    embed_color: str | None

    active: bool
    created_by: str
    last_run_at: str | None

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "EventRecord":
        return cls(
            id=row["id"],
            guild_id=row["guild_id"],
            name=row["name"],
            description=row["description"],
            channel_id=row["channel_id"],
            role_ping_id=row["role_ping_id"],
            run_at=row["run_at"],
            timezone=row["timezone"],
            repeat_type=row["repeat_type"],
            reminder_minutes=row["reminder_minutes"],
            reminder_sent=bool(row["reminder_sent"]),
            banner_url=row["banner_url"],
            thumbnail_url=row["thumbnail_url"],
            embed_color=row["embed_color"],
            active=bool(row["active"]),
            created_by=row["created_by"],
            last_run_at=row["last_run_at"],
        )
