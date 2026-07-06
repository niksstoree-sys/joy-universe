"""
Variable resolver untuk JOY UNIVERSE.

Dipakai di Welcome, Leave, dan (nanti) Event system supaya user bisa
menulis teks dengan variabel seperti {user}, {server}, {member_count}, dst,
yang otomatis diganti dengan data asli saat pesan dikirim.
"""

from __future__ import annotations

import discord


def _ordinal(n: int) -> str:
    """Contoh: 1 -> 1st, 2 -> 2nd, 21 -> 21st (dipakai untuk 'anggota ke-N')."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def build_variable_map(member: discord.Member, guild: discord.Guild) -> dict[str, str]:
    member_count = guild.member_count or 0
    return {
        "{user}": member.mention,
        "{user_mention}": member.mention,
        "{user_name}": member.name,
        "{user_display_name}": member.display_name,
        "{user_tag}": str(member),
        "{user_id}": str(member.id),
        "{user_avatar}": member.display_avatar.url,
        "{server}": guild.name,
        "{server_name}": guild.name,
        "{server_id}": str(guild.id),
        "{server_icon}": guild.icon.url if guild.icon else "",
        "{member_count}": str(member_count),
        "{member_count_ordinal}": _ordinal(member_count),
    }


def resolve_variables(text: str | None, member: discord.Member, guild: discord.Guild) -> str | None:
    """Ganti semua token {variable} di `text` dengan data asli. Aman untuk None."""
    if not text:
        return text

    result = text
    for token, value in build_variable_map(member, guild).items():
        result = result.replace(token, value)
    return result
