"""Service layer untuk Auto Role System."""

from __future__ import annotations

from bot.database.connection import Database


class AutoRoleService:
    def __init__(self, db: Database):
        self.db = db

    async def is_enabled(self, guild_id: int) -> bool:
        row = await self.db.fetchone(
            "SELECT enabled FROM auto_role_config WHERE guild_id = ?", (str(guild_id),)
        )
        if row is None:
            await self.db.execute(
                "INSERT INTO auto_role_config (guild_id) VALUES (?)", (str(guild_id),)
            )
            return True
        return bool(row["enabled"])

    async def set_enabled(self, guild_id: int, enabled: bool) -> None:
        await self.is_enabled(guild_id)  # pastikan row ada
        await self.db.execute(
            "UPDATE auto_role_config SET enabled = ? WHERE guild_id = ?",
            (int(enabled), str(guild_id)),
        )

    async def add_role(self, guild_id: int, role_id: int) -> None:
        await self.db.execute(
            "INSERT OR IGNORE INTO auto_roles (guild_id, role_id) VALUES (?, ?)",
            (str(guild_id), str(role_id)),
        )

    async def remove_role(self, guild_id: int, role_id: int) -> None:
        await self.db.execute(
            "DELETE FROM auto_roles WHERE guild_id = ? AND role_id = ?",
            (str(guild_id), str(role_id)),
        )

    async def list_roles(self, guild_id: int) -> list[str]:
        rows = await self.db.fetchall(
            "SELECT role_id FROM auto_roles WHERE guild_id = ?", (str(guild_id),)
        )
        return [r["role_id"] for r in rows]
