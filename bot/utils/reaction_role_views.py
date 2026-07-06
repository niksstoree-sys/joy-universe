"""
View builder untuk Reaction Role (button & dropdown).

PENTING: View di sini sengaja TIDAK didaftarkan callback per-item.
Semua interaksi ditangani lewat listener `on_interaction` mentah di
`bot/cogs/roles.py` (custom_id di-parse manual). Ini bikin komponennya
otomatis "persistent" walau bot restart — tanpa perlu re-register View
satu-satu saat startup, karena Discord tetap mengirim event interaksi ke
bot untuk custom_id apapun, terlepas ada View Python yang cocok atau tidak.
"""

from __future__ import annotations

import discord

from bot.models.reaction_role import ReactionRoleEntry

BUTTON_STYLE_MAP = {
    "primary": discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
}


def build_button_view(entries: list[ReactionRoleEntry]) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for entry in entries:
        style = BUTTON_STYLE_MAP.get(entry.style, discord.ButtonStyle.secondary)
        view.add_item(
            discord.ui.Button(
                label=entry.label or "Role",
                emoji=entry.emoji or None,
                style=style,
                custom_id=f"joyrr:btn:{entry.id}",
            )
        )
    return view


def build_dropdown_view(panel_id: int, entries: list[ReactionRoleEntry], unique_mode: bool) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    options = [
        discord.SelectOption(
            label=(entry.label or "Role")[:100],
            value=str(entry.id),
            emoji=entry.emoji or None,
            description=(entry.description or None),
        )
        for entry in entries
    ]
    select = discord.ui.Select(
        placeholder="Pilih role di sini...",
        min_values=0,
        max_values=1 if unique_mode else len(options),
        options=options,
        custom_id=f"joyrr:dd:{panel_id}",
    )
    view.add_item(select)
    return view
