"""
Card generator untuk Welcome & Leave (Stage 2).

Generate image card premium bertema kuning (#FFD54A), dengan avatar bulat
ber-glow, nama user, judul, dan member count. Background bisa custom
(URL gambar) atau default gradient kuning-gelap kalau tidak diisi.

Semua proses Pillow (CPU-bound) dijalankan lewat asyncio.to_thread supaya
tidak nge-block event loop bot.
"""

from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path

import aiohttp
import discord
from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger("joyuniverse.card_generator")

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
FONT_BOLD = ASSETS_DIR / "fonts" / "Poppins-Bold.ttf"
FONT_MEDIUM = ASSETS_DIR / "fonts" / "Poppins-Medium.ttf"
FONT_REGULAR = ASSETS_DIR / "fonts" / "Poppins-Regular.ttf"

CARD_WIDTH = 1000
CARD_HEIGHT = 400
AVATAR_SIZE = 176

YELLOW = (255, 213, 74)
DARK_BG = (24, 22, 18)
WHITE = (255, 255, 255)
MUTED = (210, 205, 195)


async def _fetch_bytes(url: str) -> bytes | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.read()
                logger.warning("Gagal fetch image (status %s): %s", resp.status, url)
    except Exception:
        logger.exception("Error saat fetch image: %s", url)
    return None


def _make_default_background() -> Image.Image:
    """Gradient kuning -> gelap, dipakai kalau admin tidak set background custom."""
    base = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), DARK_BG)
    gradient = Image.new("L", (1, CARD_HEIGHT), color=0xFF)
    for y in range(CARD_HEIGHT):
        gradient.putpixel((0, y), int(255 * (1 - (y / CARD_HEIGHT) ** 1.4)))
    gradient = gradient.resize((CARD_WIDTH, CARD_HEIGHT))

    overlay = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), YELLOW)
    base = Image.composite(overlay, base, gradient.point(lambda p: int(p * 0.35)))
    return base


def _circle_mask(size: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    return mask


def _avatar_x(position: str) -> int:
    padding = 60
    if position == "left":
        return padding
    if position == "right":
        return CARD_WIDTH - AVATAR_SIZE - padding
    return (CARD_WIDTH - AVATAR_SIZE) // 2  # center


def _text_anchor_y(position: str) -> tuple[int, int, int]:
    """Return (title_y, subtitle_y, footer_y) tergantung posisi teks."""
    if position == "top":
        return 40, 90, 130
    if position == "center":
        return 170, 220, 260
    return 260, 310, 350  # bottom (default)


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font_path: Path, max_size: int, max_width: int) -> ImageFont.FreeTypeFont:
    size = max_size
    while size > 14:
        font = ImageFont.truetype(str(font_path), size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size -= 2
    return ImageFont.truetype(str(font_path), 14)


def _render_card_sync(
    avatar_bytes: bytes | None,
    background_bytes: bytes | None,
    title_text: str,
    subtitle_text: str,
    footer_text: str,
    avatar_position: str,
    text_position: str,
) -> bytes:
    if background_bytes:
        try:
            bg = Image.open(io.BytesIO(background_bytes)).convert("RGB")
            bg = bg.resize((CARD_WIDTH, CARD_HEIGHT))
            # Gelapkan sedikit supaya teks tetap terbaca di atas background custom
            overlay = Image.new("RGB", bg.size, (0, 0, 0))
            bg = Image.blend(bg, overlay, 0.35)
        except Exception:
            logger.exception("Background custom gagal diproses, fallback ke default.")
            bg = _make_default_background()
    else:
        bg = _make_default_background()

    card = bg.convert("RGBA")
    draw = ImageDraw.Draw(card)

    # Border tipis kuning di sekeliling card
    draw.rectangle((4, 4, CARD_WIDTH - 5, CARD_HEIGHT - 5), outline=YELLOW + (255,), width=4)

    avatar_x = _avatar_x(avatar_position)
    avatar_y = (CARD_HEIGHT - AVATAR_SIZE) // 2

    if text_position == "top":
        avatar_y = CARD_HEIGHT - AVATAR_SIZE - 40
    elif text_position != "bottom":
        pass  # center: avatar tetap di tengah vertikal

    # Avatar + glow ring
    if avatar_bytes:
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar_img = avatar_img.resize((AVATAR_SIZE, AVATAR_SIZE))
        except Exception:
            logger.exception("Avatar gagal diproses, pakai placeholder polos.")
            avatar_img = Image.new("RGBA", (AVATAR_SIZE, AVATAR_SIZE), (60, 60, 60, 255))
    else:
        avatar_img = Image.new("RGBA", (AVATAR_SIZE, AVATAR_SIZE), (60, 60, 60, 255))

    glow_size = AVATAR_SIZE + 24
    glow = Image.new("RGBA", (glow_size, glow_size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((0, 0, glow_size, glow_size), fill=YELLOW + (255,))
    glow = glow.filter(ImageFilter.GaussianBlur(8))
    card.alpha_composite(glow, (avatar_x - 12, avatar_y - 12))

    mask = _circle_mask(AVATAR_SIZE)
    card.paste(avatar_img, (avatar_x, avatar_y), mask)

    ring = Image.new("RGBA", (AVATAR_SIZE, AVATAR_SIZE), (0, 0, 0, 0))
    ring_draw = ImageDraw.Draw(ring)
    ring_draw.ellipse((2, 2, AVATAR_SIZE - 2, AVATAR_SIZE - 2), outline=YELLOW + (255,), width=6)
    card.alpha_composite(ring, (avatar_x, avatar_y))

    # Teks: title, subtitle, footer
    title_y, subtitle_y, footer_y = _text_anchor_y(text_position)
    max_text_width = CARD_WIDTH - 100

    title_font = _fit_text(draw, title_text, FONT_BOLD, 52, max_text_width)
    subtitle_font = ImageFont.truetype(str(FONT_MEDIUM), 28)
    footer_font = ImageFont.truetype(str(FONT_REGULAR), 20)

    def centered_x(text: str, font: ImageFont.FreeTypeFont) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        return (CARD_WIDTH - (bbox[2] - bbox[0])) // 2

    draw.text((centered_x(title_text, title_font), title_y), title_text, font=title_font, fill=WHITE)
    draw.text((centered_x(subtitle_text, subtitle_font), subtitle_y), subtitle_text, font=subtitle_font, fill=YELLOW)
    draw.text((centered_x(footer_text, footer_font), footer_y), footer_text, font=footer_font, fill=MUTED)

    buffer = io.BytesIO()
    card.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


async def generate_greeting_card(
    member: discord.Member,
    guild: discord.Guild,
    *,
    kind: str,  # "welcome" atau "leave"
    background_url: str | None,
    avatar_position: str,
    text_position: str,
) -> discord.File:
    """Generate card dan kembalikan sebagai discord.File siap kirim."""
    avatar_url = member.display_avatar.replace(size=256, format="png").url

    avatar_bytes, background_bytes = await asyncio.gather(
        _fetch_bytes(avatar_url),
        _fetch_bytes(background_url) if background_url else asyncio.sleep(0, result=None),
    )

    title_text = "Selamat Datang!" if kind == "welcome" else "Sampai Jumpa!"
    subtitle_text = member.display_name
    member_count = guild.member_count or 0
    footer_text = (
        f"Member ke-{member_count} di {guild.name}"
        if kind == "welcome"
        else f"Sekarang {member_count} member di {guild.name}"
    )

    image_bytes = await asyncio.to_thread(
        _render_card_sync,
        avatar_bytes,
        background_bytes,
        title_text,
        subtitle_text,
        footer_text,
        avatar_position,
        text_position,
    )

    filename = f"{kind}_{member.id}.png"
    return discord.File(io.BytesIO(image_bytes), filename=filename)
