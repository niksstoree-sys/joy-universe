"""Model data untuk Reaction Role System."""

from __future__ import annotations

from dataclasses import dataclass

import aiosqlite


@dataclass
class ReactionRolePanel:
    id: int
    guild_id: str
    channel_id: str | None
    message_id: str | None
    panel_type: str
    title: str
    description: str | None
    color: str | None
    unique_mode: bool
    verification_mode: bool
    created_by: str

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "ReactionRolePanel":
        return cls(
            id=row["id"],
            guild_id=row["guild_id"],
            channel_id=row["channel_id"],
            message_id=row["message_id"],
            panel_type=row["panel_type"],
            title=row["title"],
            description=row["description"],
            color=row["color"],
            unique_mode=bool(row["unique_mode"]),
            verification_mode=bool(row["verification_mode"]),
            created_by=row["created_by"],
        )


@dataclass
class ReactionRoleEntry:
    id: int
    panel_id: int
    role_id: str
    emoji: str | None
    label: str | None
    style: str
    description: str | None
    position: int

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "ReactionRoleEntry":
        return cls(
            id=row["id"],
            panel_id=row["panel_id"],
            role_id=row["role_id"],
            emoji=row["emoji"],
            label=row["label"],
            style=row["style"],
            description=row["description"],
            position=row["position"],
        )
