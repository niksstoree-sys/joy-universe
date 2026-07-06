"""Service layer untuk Reaction Role System (panel + entry CRUD)."""

from __future__ import annotations

from bot.database.connection import Database
from bot.models.reaction_role import ReactionRoleEntry, ReactionRolePanel

VALID_PANEL_TYPES = {"button", "reaction", "dropdown"}
VALID_STYLES = {"primary", "secondary", "success", "danger"}


class ReactionRoleService:
    def __init__(self, db: Database):
        self.db = db

    # ---------- Panel ----------

    async def create_panel(
        self,
        *,
        guild_id: int,
        panel_type: str,
        title: str,
        description: str | None,
        color: str | None,
        created_by: int,
        unique_mode: bool = False,
        verification_mode: bool = False,
    ) -> int:
        if panel_type not in VALID_PANEL_TYPES:
            raise ValueError(f"panel_type harus salah satu dari: {', '.join(VALID_PANEL_TYPES)}")

        await self.db.connection.execute(
            """
            INSERT INTO reaction_role_panels
                (guild_id, panel_type, title, description, color, unique_mode, verification_mode, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(guild_id), panel_type, title, description, color,
                int(unique_mode), int(verification_mode), str(created_by),
            ),
        )
        await self.db.connection.commit()
        row = await self.db.fetchone("SELECT last_insert_rowid() AS id")
        return int(row["id"])

    async def get_panel(self, panel_id: int, guild_id: int) -> ReactionRolePanel | None:
        row = await self.db.fetchone(
            "SELECT * FROM reaction_role_panels WHERE id = ? AND guild_id = ?",
            (panel_id, str(guild_id)),
        )
        return ReactionRolePanel.from_row(row) if row else None

    async def get_panel_by_message(self, message_id: int) -> ReactionRolePanel | None:
        row = await self.db.fetchone(
            "SELECT * FROM reaction_role_panels WHERE message_id = ?", (str(message_id),)
        )
        return ReactionRolePanel.from_row(row) if row else None

    async def list_panels(self, guild_id: int) -> list[ReactionRolePanel]:
        rows = await self.db.fetchall(
            "SELECT * FROM reaction_role_panels WHERE guild_id = ? ORDER BY id ASC", (str(guild_id),)
        )
        return [ReactionRolePanel.from_row(r) for r in rows]

    async def delete_panel(self, panel_id: int, guild_id: int) -> bool:
        panel = await self.get_panel(panel_id, guild_id)
        if panel is None:
            return False
        await self.db.execute("DELETE FROM reaction_role_entries WHERE panel_id = ?", (panel_id,))
        await self.db.execute("DELETE FROM reaction_role_panels WHERE id = ?", (panel_id,))
        return True

    async def set_message_id(self, panel_id: int, channel_id: int, message_id: int) -> None:
        await self.db.execute(
            "UPDATE reaction_role_panels SET channel_id = ?, message_id = ?, updated_at = datetime('now') WHERE id = ?",
            (str(channel_id), str(message_id), panel_id),
        )

    async def set_panel_flag(self, panel_id: int, guild_id: int, column: str, value: bool) -> bool:
        if column not in ("unique_mode", "verification_mode"):
            raise ValueError("Kolom tidak diizinkan diubah.")
        panel = await self.get_panel(panel_id, guild_id)
        if panel is None:
            return False
        await self.db.execute(
            f"UPDATE reaction_role_panels SET {column} = ?, updated_at = datetime('now') WHERE id = ?",
            (int(value), panel_id),
        )
        return True

    # ---------- Entry ----------

    async def add_entry(
        self,
        *,
        panel_id: int,
        role_id: int,
        emoji: str | None = None,
        label: str | None = None,
        style: str = "secondary",
        description: str | None = None,
    ) -> int:
        if style not in VALID_STYLES:
            style = "secondary"

        row = await self.db.fetchone(
            "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM reaction_role_entries WHERE panel_id = ?",
            (panel_id,),
        )
        position = row["next_pos"]

        await self.db.connection.execute(
            """
            INSERT INTO reaction_role_entries (panel_id, role_id, emoji, label, style, description, position)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (panel_id, str(role_id), emoji, label, style, description, position),
        )
        await self.db.connection.commit()
        result = await self.db.fetchone("SELECT last_insert_rowid() AS id")
        return int(result["id"])

    async def remove_entry(self, entry_id: int) -> bool:
        row = await self.db.fetchone("SELECT id FROM reaction_role_entries WHERE id = ?", (entry_id,))
        if row is None:
            return False
        await self.db.execute("DELETE FROM reaction_role_entries WHERE id = ?", (entry_id,))
        return True

    async def get_entries(self, panel_id: int) -> list[ReactionRoleEntry]:
        rows = await self.db.fetchall(
            "SELECT * FROM reaction_role_entries WHERE panel_id = ? ORDER BY position ASC", (panel_id,)
        )
        return [ReactionRoleEntry.from_row(r) for r in rows]

    async def get_entry_by_id(self, entry_id: int) -> ReactionRoleEntry | None:
        row = await self.db.fetchone("SELECT * FROM reaction_role_entries WHERE id = ?", (entry_id,))
        return ReactionRoleEntry.from_row(row) if row else None
