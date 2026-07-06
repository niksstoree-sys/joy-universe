"""
Greeting message builder untuk JOY UNIVERSE.

Menggabungkan semua konfigurasi (embed, card, button, content, mention)
dari GreetingConfig menjadi satu pesan Discord yang siap dikirim.
Dipakai oleh event listener (on_member_join/remove) dan command `test`.
"""

from __future__ import annotations

import discord

from bot.core.config import config as bot_config
from bot.models.greeting import GreetingConfig
from bot.utils.card_generator import generate_greeting_card
from bot.utils.embeds import JoyEmbed
from bot.utils.variables import resolve_variables


async def send_greeting_message(
    channel: discord.abc.Messageable,
    greeting: GreetingConfig,
    member: discord.Member,
    guild: discord.Guild,
    *,
    kind: str,  # "welcome" atau "leave"
) -> discord.Message | None:
    def resolve(text: str | None) -> str | None:
        return resolve_variables(text, member, guild)

    content = resolve(greeting.content)
    if greeting.mention_user:
        content = f"{member.mention} {content}" if content else member.mention

    embed: discord.Embed | None = None
    if greeting.embed_enabled:
        color = (
            int(greeting.embed_color.lstrip("#"), 16)
            if greeting.embed_color
            else bot_config.default_color
        )
        embed = JoyEmbed(
            title=resolve(greeting.embed_title),
            description=resolve(greeting.embed_description),
            color=color,
        )

        thumbnail = resolve(greeting.embed_thumbnail)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)

        banner = resolve(greeting.embed_image)
        if banner:
            embed.set_image(url=banner)

        if greeting.embed_author_name:
            embed.set_author(
                name=resolve(greeting.embed_author_name),
                icon_url=resolve(greeting.embed_author_icon) or discord.utils.MISSING,
            )

        if greeting.embed_footer_text:
            embed.set_footer(
                text=resolve(greeting.embed_footer_text),
                icon_url=resolve(greeting.embed_footer_icon) or discord.utils.MISSING,
            )

        if not greeting.embed_timestamp:
            embed.timestamp = None  # type: ignore[assignment]

    file: discord.File | None = None
    if greeting.card_enabled:
        file = await generate_greeting_card(
            member,
            guild,
            kind=kind,
            background_url=greeting.card_background,
            avatar_position=greeting.card_avatar_position,
            text_position=greeting.card_text_position,
        )
        if embed is not None:
            embed.set_image(url=f"attachment://{file.filename}")

    view: discord.ui.View | None = None
    if greeting.button_label and greeting.button_url:
        view = discord.ui.View(timeout=None)
        view.add_item(
            discord.ui.Button(
                label=greeting.button_label,
                url=greeting.button_url,
                style=discord.ButtonStyle.link,
            )
        )

    if content is None and embed is None and file is None:
        return None  # tidak ada konten yang dikonfigurasi, tidak usah kirim apa-apa

    send_kwargs: dict = {}
    if content:
        send_kwargs["content"] = content
    if embed is not None:
        send_kwargs["embed"] = embed
    if file is not None:
        send_kwargs["file"] = file
    if view is not None:
        send_kwargs["view"] = view

    return await channel.send(**send_kwargs)
