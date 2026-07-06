"""
Rank Card & Leaderboard Card generator untuk Leveling System (Stage 4).

Menggunakan helper (fetch image, font, warna) yang sama dengan
card_generator.py (welcome/leave) supaya konsisten temanya (#FFD54A).
Semua render Pillow dijalankan lewat asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
import io
import logging

import discord
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from bot.utils.card_generator import (
    DARK_BG,
    FONT_BOLD,
    FONT_MEDIUM,
    FONT_REGULAR,
    MUTED,
    WHITE,
    YELLOW,
    _circle_mask,
    _fetch_bytes,
    _make_default_background,
)

logger = logging.getLogger("joyuniverse.rank_card")

RANK_CARD_WIDTH = 1000
RANK_CARD_HEIGHT = 300
RANK_AVATAR_SIZE = 160

LB_WIDTH = 900
LB_ROW_HEIGHT = 84
LB_HEADER_HEIGHT = 110
LB_AVATAR_SIZE = 56


def _draw_progress_bar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    height: int,
    progress: float,
    bg_color: tuple = (60, 55, 45, 255),
    fill_color: tuple = YELLOW,
) -> None:
    progress = max(0.0, min(1.0, progress))
    radius = height // 2

    draw.rounded_rectangle((x, y, x + width, y + height), radius=radius, fill=bg_color)
    fill_width = int(width * progress)
    if fill_width > radius * 2:
        draw.rounded_rectangle((x, y, x + fill_width, y + height), radius=radius, fill=fill_color)
    elif fill_width > 0:
        draw.ellipse((x, y, x + height, y + height), fill=fill_color)


def _render_rank_card_sync(
    avatar_bytes: bytes | None,
    background_bytes: bytes | None,
    username: str,
    level: int,
    prestige: int,
    rank: int,
    xp_into: int,
    xp_needed: int,
    total_messages: int,
    voice_minutes: int,
) -> bytes:
    if background_bytes:
        try:
            bg = Image.open(io.BytesIO(background_bytes)).convert("RGB").resize((RANK_CARD_WIDTH, RANK_CARD_HEIGHT))
            overlay = Image.new("RGB", bg.size, (0, 0, 0))
            bg = Image.blend(bg, overlay, 0.4)
        except Exception:
            logger.exception("Background rank card custom gagal diproses, fallback ke default.")
            bg = _make_default_background()
            bg = bg.resize((RANK_CARD_WIDTH, RANK_CARD_HEIGHT))
    else:
        bg = _make_default_background()
        bg = bg.resize((RANK_CARD_WIDTH, RANK_CARD_HEIGHT))

    card = bg.convert("RGBA")
    draw = ImageDraw.Draw(card)
    draw.rectangle((4, 4, RANK_CARD_WIDTH - 5, RANK_CARD_HEIGHT - 5), outline=YELLOW + (255,), width=4)

    avatar_x, avatar_y = 60, (RANK_CARD_HEIGHT - RANK_AVATAR_SIZE) // 2

    if avatar_bytes:
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((RANK_AVATAR_SIZE, RANK_AVATAR_SIZE))
        except Exception:
            avatar_img = Image.new("RGBA", (RANK_AVATAR_SIZE, RANK_AVATAR_SIZE), (60, 60, 60, 255))
    else:
        avatar_img = Image.new("RGBA", (RANK_AVATAR_SIZE, RANK_AVATAR_SIZE), (60, 60, 60, 255))

    glow_size = RANK_AVATAR_SIZE + 20
    glow = Image.new("RGBA", (glow_size, glow_size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((0, 0, glow_size, glow_size), fill=YELLOW + (255,))
    glow = glow.filter(ImageFilter.GaussianBlur(7))
    card.alpha_composite(glow, (avatar_x - 10, avatar_y - 10))

    mask = _circle_mask(RANK_AVATAR_SIZE)
    card.paste(avatar_img, (avatar_x, avatar_y), mask)

    ring = Image.new("RGBA", (RANK_AVATAR_SIZE, RANK_AVATAR_SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((2, 2, RANK_AVATAR_SIZE - 2, RANK_AVATAR_SIZE - 2), outline=YELLOW + (255,), width=5)
    card.alpha_composite(ring, (avatar_x, avatar_y))

    if prestige > 0:
        badge_text = f"P{prestige}"
        badge_font = ImageFont.truetype(str(FONT_BOLD), 22)
        badge_size = 44
        badge_x = avatar_x + RANK_AVATAR_SIZE - badge_size + 6
        badge_y = avatar_y + RANK_AVATAR_SIZE - badge_size + 6
        draw.ellipse((badge_x, badge_y, badge_x + badge_size, badge_y + badge_size), fill=YELLOW + (255,), outline=DARK_BG + (255,), width=3)
        bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            (badge_x + (badge_size - tw) // 2, badge_y + (badge_size - th) // 2 - bbox[1]),
            badge_text, font=badge_font, fill=DARK_BG,
        )

    text_x = avatar_x + RANK_AVATAR_SIZE + 40
    username_font = ImageFont.truetype(str(FONT_BOLD), 40)
    name_display = username if len(username) <= 20 else username[:18] + "…"
    draw.text((text_x, 48), name_display, font=username_font, fill=WHITE)

    sub_font = ImageFont.truetype(str(FONT_MEDIUM), 24)
    draw.text((text_x, 100), f"Level {level}  •  Rank #{rank}", font=sub_font, fill=YELLOW)

    stats_font = ImageFont.truetype(str(FONT_REGULAR), 18)
    draw.text(
        (text_x, 136),
        f"{total_messages:,} pesan  •  {voice_minutes:,} menit voice".replace(",", "."),
        font=stats_font, fill=MUTED,
    )

    bar_width = RANK_CARD_WIDTH - text_x - 60
    bar_y = 190
    progress = xp_into / xp_needed if xp_needed > 0 else 0
    _draw_progress_bar(draw, text_x, bar_y, bar_width, 26, progress)

    xp_font = ImageFont.truetype(str(FONT_REGULAR), 18)
    xp_text = f"{xp_into:,} / {xp_needed:,} XP".replace(",", ".")
    draw.text((text_x, bar_y + 34), xp_text, font=xp_font, fill=MUTED)

    buffer = io.BytesIO()
    card.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


async def generate_rank_card(
    member: discord.Member,
    *,
    level: int,
    prestige: int,
    rank: int,
    xp_into: int,
    xp_needed: int,
    total_messages: int,
    voice_minutes: int,
    background_url: str | None,
) -> discord.File:
    avatar_url = member.display_avatar.replace(size=256, format="png").url
    avatar_bytes, background_bytes = await asyncio.gather(
        _fetch_bytes(avatar_url),
        _fetch_bytes(background_url) if background_url else asyncio.sleep(0, result=None),
    )

    image_bytes = await asyncio.to_thread(
        _render_rank_card_sync,
        avatar_bytes,
        background_bytes,
        member.display_name,
        level,
        prestige,
        rank,
        xp_into,
        xp_needed,
        total_messages,
        voice_minutes,
    )
    return discord.File(io.BytesIO(image_bytes), filename=f"rank_{member.id}.png")


def _render_leaderboard_card_sync(
    background_bytes: bytes | None,
    guild_name: str,
    entries: list[dict],  # each: {"rank", "avatar_bytes", "display_name", "level", "prestige", "xp"}
) -> bytes:
    height = LB_HEADER_HEIGHT + LB_ROW_HEIGHT * len(entries) + 20

    if background_bytes:
        try:
            bg = Image.open(io.BytesIO(background_bytes)).convert("RGB").resize((LB_WIDTH, height))
            overlay = Image.new("RGB", bg.size, (0, 0, 0))
            bg = Image.blend(bg, overlay, 0.45)
        except Exception:
            bg = Image.new("RGB", (LB_WIDTH, height), DARK_BG)
    else:
        bg = Image.new("RGB", (LB_WIDTH, height), DARK_BG)

    card = bg.convert("RGBA")
    draw = ImageDraw.Draw(card)
    draw.rectangle((4, 4, LB_WIDTH - 5, height - 5), outline=YELLOW + (255,), width=4)

    title_font = ImageFont.truetype(str(FONT_BOLD), 34)
    draw.text((36, 24), f"Leaderboard — {guild_name}", font=title_font, fill=WHITE)

    rank_font = ImageFont.truetype(str(FONT_BOLD), 26)
    name_font = ImageFont.truetype(str(FONT_MEDIUM), 22)
    sub_font = ImageFont.truetype(str(FONT_REGULAR), 16)

    y = LB_HEADER_HEIGHT
    for entry in entries:
        rank = entry["rank"]
        rank_color = YELLOW if rank <= 3 else MUTED

        draw.text((40, y + LB_ROW_HEIGHT // 2 - 16), f"#{rank}", font=rank_font, fill=rank_color)

        avatar_x = 110
        avatar_y = y + (LB_ROW_HEIGHT - LB_AVATAR_SIZE) // 2
        avatar_bytes = entry.get("avatar_bytes")
        if avatar_bytes:
            try:
                avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((LB_AVATAR_SIZE, LB_AVATAR_SIZE))
            except Exception:
                avatar_img = Image.new("RGBA", (LB_AVATAR_SIZE, LB_AVATAR_SIZE), (60, 60, 60, 255))
        else:
            avatar_img = Image.new("RGBA", (LB_AVATAR_SIZE, LB_AVATAR_SIZE), (60, 60, 60, 255))

        mask = _circle_mask(LB_AVATAR_SIZE)
        card.paste(avatar_img, (avatar_x, avatar_y), mask)
        ring = Image.new("RGBA", (LB_AVATAR_SIZE, LB_AVATAR_SIZE), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse((1, 1, LB_AVATAR_SIZE - 1, LB_AVATAR_SIZE - 1), outline=YELLOW + (255,), width=3)
        card.alpha_composite(ring, (avatar_x, avatar_y))

        text_x = avatar_x + LB_AVATAR_SIZE + 24
        name = entry["display_name"]
        name_display = name if len(name) <= 24 else name[:22] + "…"
        draw.text((text_x, y + 14), name_display, font=name_font, fill=WHITE)

        prestige_str = f"P{entry['prestige']} • " if entry["prestige"] > 0 else ""
        draw.text(
            (text_x, y + 44),
            f"{prestige_str}Level {entry['level']}  •  {entry['xp']:,} XP".replace(",", "."),
            font=sub_font, fill=MUTED,
        )

        y += LB_ROW_HEIGHT
        if entry is not entries[-1]:
            draw.line((40, y, LB_WIDTH - 40, y), fill=(255, 255, 255, 30), width=1)

    buffer = io.BytesIO()
    card.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


async def generate_leaderboard_card(
    guild: discord.Guild,
    entries: list[dict],  # each: {"rank", "member_or_none", "display_name", "level", "prestige", "xp"}
    *,
    background_url: str | None,
) -> discord.File:
    avatar_urls = [
        e["member"].display_avatar.replace(size=128, format="png").url if e.get("member") else None
        for e in entries
    ]

    fetch_tasks = [
        _fetch_bytes(url) if url else asyncio.sleep(0, result=None) for url in avatar_urls
    ]
    background_task = _fetch_bytes(background_url) if background_url else asyncio.sleep(0, result=None)

    results = await asyncio.gather(*fetch_tasks, background_task)
    avatar_bytes_list = results[:-1]
    background_bytes = results[-1]

    render_entries = []
    for entry, avatar_bytes in zip(entries, avatar_bytes_list):
        render_entries.append({
            "rank": entry["rank"],
            "avatar_bytes": avatar_bytes,
            "display_name": entry["display_name"],
            "level": entry["level"],
            "prestige": entry["prestige"],
            "xp": entry["xp"],
        })

    image_bytes = await asyncio.to_thread(
        _render_leaderboard_card_sync, background_bytes, guild.name, render_entries
    )
    return discord.File(io.BytesIO(image_bytes), filename=f"leaderboard_{guild.id}.png")
