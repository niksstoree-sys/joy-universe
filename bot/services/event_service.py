"""
Service layer untuk Event System.

Menangani semua akses database ke tabel `events`: create, edit, cancel,
list, dan query event yang sudah waktunya jalan (dipakai oleh scheduler).
"""

from __future__ import annotations

from datetime import datetime

from bot.database.connection import Database
from bot.models.event import EventRecord
from bot.utils.datetime_utils import now_db_string, utc_to_db_string

EDITABLE_FIELDS = {
    "description",
    "role_ping_id",
    "repeat_type",
    "reminder_minutes",
    "banner_url",
    "thumbnail_url",
    "embed_color",
    "channel_id",
}


class EventService:
    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        *,
        guild_id: int,
        name: str,
        channel_id: int,
        run_at_utc: datetime,
        tz_name: str,
        created_by: int,
        description: str | None = None,
        role_ping_id: int | None = None,
        repeat_type: str = "once",
        reminder_minutes: int | None = None,
        banner_url: str | None = None,
        thumbnail_url: str | None = None,
        embed_color: str | None = None,
    ) -> int:
        cursor_query = """
            INSERT INTO events (
                guild_id, name, description, channel_id, role_ping_id,
                run_at, timezone, repeat_type, reminder_minutes,
                banner_url, thumbnail_url, embed_color, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            str(guild_id),
            name,
            description,
            str(channel_id),
            str(role_ping_id) if role_ping_id else None,
            utc_to_db_string(run_at_utc),
            tz_name,
            repeat_type,
            reminder_minutes,
            banner_url,
            thumbnail_url,
            embed_color,
            str(created_by),
        )
        await self.db.connection.execute(cursor_query, params)
        await self.db.connection.commit()

        row = await self.db.fetchone("SELECT last_insert_rowid() AS id")
        return int(row["id"])

    async def get(self, event_id: int, guild_id: int) -> EventRecord | None:
        row = await self.db.fetchone(
            "SELECT * FROM events WHERE id = ? AND guild_id = ?", (event_id, str(guild_id))
        )
        return EventRecord.from_row(row) if row else None

    async def list_active(self, guild_id: int) -> list[EventRecord]:
        rows = await self.db.fetchall(
            "SELECT * FROM events WHERE guild_id = ? AND active = 1 ORDER BY run_at ASC",
            (str(guild_id),),
        )
        return [EventRecord.from_row(r) for r in rows]

    async def cancel(self, event_id: int, guild_id: int) -> bool:
        event = await self.get(event_id, guild_id)
        if event is None:
            return False
        await self.db.execute(
            "UPDATE events SET active = 0, updated_at = datetime('now') WHERE id = ?", (event_id,)
        )
        return True

    async def set_field(self, event_id: int, guild_id: int, column: str, value) -> bool:
        if column not in EDITABLE_FIELDS:
            raise ValueError(f"Kolom '{column}' tidak diizinkan diubah.")
        event = await self.get(event_id, guild_id)
        if event is None:
            return False
        await self.db.execute(
            f"UPDATE events SET {column} = ?, updated_at = datetime('now') WHERE id = ?",
            (value, event_id),
        )
        return True

    async def reschedule(self, event_id: int, guild_id: int, run_at_utc: datetime, tz_name: str) -> bool:
        event = await self.get(event_id, guild_id)
        if event is None:
            return False
        await self.db.execute(
            """
            UPDATE events
            SET run_at = ?, timezone = ?, reminder_sent = 0, updated_at = datetime('now')
            WHERE id = ?
            """,
            (utc_to_db_string(run_at_utc), tz_name, event_id),
        )
        return True

    # ---------- Dipakai scheduler ----------

    async def get_due_events(self) -> list[EventRecord]:
        rows = await self.db.fetchall(
            "SELECT * FROM events WHERE active = 1 AND run_at <= ? ORDER BY run_at ASC",
            (now_db_string(),),
        )
        return [EventRecord.from_row(r) for r in rows]

    async def get_due_reminders(self) -> list[EventRecord]:
        rows = await self.db.fetchall(
            """
            SELECT * FROM events
            WHERE active = 1
              AND reminder_minutes IS NOT NULL
              AND reminder_sent = 0
              AND datetime(run_at, '-' || reminder_minutes || ' minutes') <= ?
              AND run_at > ?
            ORDER BY run_at ASC
            """,
            (now_db_string(), now_db_string()),
        )
        return [EventRecord.from_row(r) for r in rows]

    async def mark_reminder_sent(self, event_id: int) -> None:
        await self.db.execute("UPDATE events SET reminder_sent = 1 WHERE id = ?", (event_id,))

    async def advance_or_deactivate(self, event_id: int, next_run_at_utc: datetime | None) -> None:
        if next_run_at_utc is None:
            await self.db.execute(
                """
                UPDATE events
                SET active = 0, last_run_at = datetime('now'), updated_at = datetime('now')
                WHERE id = ?
                """,
                (event_id,),
            )
        else:
            await self.db.execute(
                """
                UPDATE events
                SET run_at = ?, reminder_sent = 0, last_run_at = datetime('now'), updated_at = datetime('now')
                WHERE id = ?
                """,
                (utc_to_db_string(next_run_at_utc), event_id),
            )
