"""
Cog Leave System untuk JOY UNIVERSE.

Struktur identik dengan Welcome System (Stage 2), hanya beda tabel
(`leave_config`) dan event trigger (`on_member_remove`).
"""

from __future__ import annotations

import logging
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.bot import JoyUniverse
from bot.services.greeting_service import GreetingService
from bot.utils.embeds import JoyEmbed
from bot.utils.emojis import emoji
from bot.utils.greeting_builder import send_greeting_message

logger = logging.getLogger("joyuniverse.cogs.leave")

POSITION_CHOICES = ["left", "center", "right"]
TEXT_POSITION_CHOICES = ["top", "center", "bottom"]

VARIABLES_HELP = (
    "`{user}` / `{user_mention}` — mention user\n"
    "`{user_name}` — username\n"
    "`{user_display_name}` — nickname/display name\n"
    "`{user_tag}` — nama#tag lengkap\n"
    "`{user_id}` — ID user\n"
    "`{user_avatar}` — URL avatar user\n"
    "`{server}` / `{server_name}` — nama server\n"
    "`{server_id}` — ID server\n"
    "`{server_icon}` — URL icon server\n"
    "`{member_count}` — jumlah member sekarang\n"
    "`{member_count_ordinal}` — contoh: 42nd"
)


def _manage_guild_prefix():
    return commands.has_permissions(manage_guild=True)


def _manage_guild_slash():
    return app_commands.checks.has_permissions(manage_guild=True)


class Leave(commands.GroupCog, name="leave"):
    """Slash commands otomatis ter-grup di bawah `/leave`."""

    def __init__(self, bot: JoyUniverse):
        self.bot = bot
        self.service = GreetingService(bot.db, "leave_config")

    # ================= EVENT LISTENER =================

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        try:
            greeting = await self.service.get(member.guild.id)
            if not greeting.enabled or not greeting.channel_id:
                return

            channel = member.guild.get_channel(int(greeting.channel_id))
            if channel is None:
                return

            await send_greeting_message(channel, greeting, member, member.guild, kind="leave")
        except Exception:
            logger.exception("Gagal mengirim leave message di guild %s", member.guild.id)

    async def _confirm(self, description: str) -> discord.Embed:
        return JoyEmbed.success(description)

    # ================= PREFIX COMMAND GROUP =================

    @commands.group(name="leave", invoke_without_command=True)
    @commands.guild_only()
    async def leave_group(self, ctx: commands.Context):
        """Menampilkan ringkasan konfigurasi leave server ini."""
        greeting = await self.service.get(ctx.guild.id)
        embed = JoyEmbed.info(
            f"**Status:** {'Aktif' if greeting.enabled else 'Nonaktif'}\n"
            f"**Channel:** {f'<#{greeting.channel_id}>' if greeting.channel_id else 'Belum diset'}\n"
            f"**Embed:** {'Aktif' if greeting.embed_enabled else 'Nonaktif'}\n"
            f"**Card:** {'Aktif' if greeting.card_enabled else 'Nonaktif'}\n\n"
            f"Gunakan `!leave test` untuk preview, atau `!help leave` untuk daftar lengkap subcommand.",
            title=f"{emoji.settings} Konfigurasi Leave",
        )
        await ctx.send(embed=embed)

    @leave_group.command(name="toggle")
    @_manage_guild_prefix()
    async def leave_toggle(self, ctx: commands.Context, state: str):
        state = state.lower()
        if state not in ("on", "off"):
            await ctx.send(embed=JoyEmbed.error("Gunakan `on` atau `off`."))
            return
        await self.service.set_enabled(ctx.guild.id, state == "on")
        await ctx.send(embed=await self._confirm(f"Leave system sekarang **{state.upper()}**."))

    @leave_group.command(name="channel")
    @_manage_guild_prefix()
    async def leave_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await self.service.set_field(ctx.guild.id, "channel_id", str(channel.id))
        await ctx.send(embed=await self._confirm(f"Channel leave diset ke {channel.mention}."))

    @leave_group.command(name="content")
    @_manage_guild_prefix()
    async def leave_content(self, ctx: commands.Context, *, text: str):
        value = None if text.lower() == "none" else text
        await self.service.set_field(ctx.guild.id, "content", value)
        await ctx.send(embed=await self._confirm("Teks pesan leave diperbarui."))

    @leave_group.command(name="title")
    @_manage_guild_prefix()
    async def leave_title(self, ctx: commands.Context, *, text: str):
        await self.service.set_field(ctx.guild.id, "embed_title", text)
        await ctx.send(embed=await self._confirm("Title embed diperbarui."))

    @leave_group.command(name="description")
    @_manage_guild_prefix()
    async def leave_description(self, ctx: commands.Context, *, text: str):
        await self.service.set_field(ctx.guild.id, "embed_description", text)
        await ctx.send(embed=await self._confirm("Description embed diperbarui."))

    @leave_group.command(name="color")
    @_manage_guild_prefix()
    async def leave_color(self, ctx: commands.Context, hex_color: str):
        try:
            int(hex_color.lstrip("#"), 16)
        except ValueError:
            await ctx.send(embed=JoyEmbed.error("Format warna tidak valid. Contoh: `#FFD54A`"))
            return
        await self.service.set_field(ctx.guild.id, "embed_color", hex_color)
        await ctx.send(embed=await self._confirm(f"Warna embed diset ke `{hex_color}`."))

    @leave_group.command(name="footer")
    @_manage_guild_prefix()
    async def leave_footer(self, ctx: commands.Context, text: str, icon_url: str | None = None):
        await self.service.set_field(ctx.guild.id, "embed_footer_text", text)
        if icon_url:
            await self.service.set_field(ctx.guild.id, "embed_footer_icon", icon_url)
        await ctx.send(embed=await self._confirm("Footer embed diperbarui."))

    @leave_group.command(name="thumbnail")
    @_manage_guild_prefix()
    async def leave_thumbnail(self, ctx: commands.Context, url: str):
        value = "{user_avatar}" if url.lower() == "avatar" else url
        await self.service.set_field(ctx.guild.id, "embed_thumbnail", value)
        await ctx.send(embed=await self._confirm("Thumbnail embed diperbarui."))

    @leave_group.command(name="image")
    @_manage_guild_prefix()
    async def leave_image(self, ctx: commands.Context, url: str):
        value = None if url.lower() == "none" else url
        await self.service.set_field(ctx.guild.id, "embed_image", value)
        await ctx.send(embed=await self._confirm("Banner/image embed diperbarui."))

    @leave_group.command(name="author")
    @_manage_guild_prefix()
    async def leave_author(self, ctx: commands.Context, name: str, icon_url: str | None = None):
        await self.service.set_field(ctx.guild.id, "embed_author_name", name)
        if icon_url:
            await self.service.set_field(ctx.guild.id, "embed_author_icon", icon_url)
        await ctx.send(embed=await self._confirm("Author embed diperbarui."))

    @leave_group.command(name="timestamp")
    @_manage_guild_prefix()
    async def leave_timestamp(self, ctx: commands.Context, state: str):
        await self.service.set_field(ctx.guild.id, "embed_timestamp", int(state.lower() == "on"))
        await ctx.send(embed=await self._confirm(f"Timestamp embed: **{state.upper()}**."))

    @leave_group.command(name="card")
    @_manage_guild_prefix()
    async def leave_card(self, ctx: commands.Context, state: str):
        await self.service.set_field(ctx.guild.id, "card_enabled", int(state.lower() == "on"))
        await ctx.send(embed=await self._confirm(f"Leave card: **{state.upper()}**."))

    @leave_group.command(name="cardbackground")
    @_manage_guild_prefix()
    async def leave_cardbackground(self, ctx: commands.Context, url: str):
        value = None if url.lower() == "none" else url
        await self.service.set_field(ctx.guild.id, "card_background", value)
        await ctx.send(embed=await self._confirm("Background card diperbarui."))

    @leave_group.command(name="avatarposition")
    @_manage_guild_prefix()
    async def leave_avatarposition(self, ctx: commands.Context, position: str):
        position = position.lower()
        if position not in POSITION_CHOICES:
            await ctx.send(embed=JoyEmbed.error(f"Pilihan: {', '.join(POSITION_CHOICES)}"))
            return
        await self.service.set_field(ctx.guild.id, "card_avatar_position", position)
        await ctx.send(embed=await self._confirm(f"Posisi avatar di card: **{position}**."))

    @leave_group.command(name="textposition")
    @_manage_guild_prefix()
    async def leave_textposition(self, ctx: commands.Context, position: str):
        position = position.lower()
        if position not in TEXT_POSITION_CHOICES:
            await ctx.send(embed=JoyEmbed.error(f"Pilihan: {', '.join(TEXT_POSITION_CHOICES)}"))
            return
        await self.service.set_field(ctx.guild.id, "card_text_position", position)
        await ctx.send(embed=await self._confirm(f"Posisi teks di card: **{position}**."))

    @leave_group.command(name="button")
    @_manage_guild_prefix()
    async def leave_button(self, ctx: commands.Context, label: str, url: str):
        await self.service.set_field(ctx.guild.id, "button_label", label)
        await self.service.set_field(ctx.guild.id, "button_url", url)
        await ctx.send(embed=await self._confirm(f"Button `{label}` ditambahkan ke leave message."))

    @leave_group.command(name="removebutton")
    @_manage_guild_prefix()
    async def leave_removebutton(self, ctx: commands.Context):
        await self.service.set_field(ctx.guild.id, "button_label", None)
        await self.service.set_field(ctx.guild.id, "button_url", None)
        await ctx.send(embed=await self._confirm("Button leave dihapus."))

    @leave_group.command(name="test")
    @_manage_guild_prefix()
    async def leave_test(self, ctx: commands.Context):
        greeting = await self.service.get(ctx.guild.id)
        message = await send_greeting_message(ctx.channel, greeting, ctx.author, ctx.guild, kind="leave")
        if message is None:
            await ctx.send(embed=JoyEmbed.warning("Tidak ada konten yang dikonfigurasi (embed, card, atau content semua nonaktif)."))

    @leave_group.command(name="reset")
    @_manage_guild_prefix()
    async def leave_reset(self, ctx: commands.Context):
        await self.service.reset(ctx.guild.id)
        await ctx.send(embed=await self._confirm("Konfigurasi leave dikembalikan ke default."))

    @leave_group.command(name="variables")
    async def leave_variables(self, ctx: commands.Context):
        await ctx.send(embed=JoyEmbed.info(VARIABLES_HELP, title=f"{emoji.info} Custom Variables"))

    # ================= SLASH COMMAND (auto grouped: /leave ...) =================

    @app_commands.command(name="settings", description="Menampilkan ringkasan konfigurasi leave.")
    async def leave_settings_slash(self, interaction: discord.Interaction):
        greeting = await self.service.get(interaction.guild_id)
        embed = JoyEmbed.info(
            f"**Status:** {'Aktif' if greeting.enabled else 'Nonaktif'}\n"
            f"**Channel:** {f'<#{greeting.channel_id}>' if greeting.channel_id else 'Belum diset'}\n"
            f"**Embed:** {'Aktif' if greeting.embed_enabled else 'Nonaktif'}\n"
            f"**Card:** {'Aktif' if greeting.card_enabled else 'Nonaktif'}\n",
            title=f"{emoji.settings} Konfigurasi Leave",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="toggle", description="Aktifkan/nonaktifkan leave system.")
    @_manage_guild_slash()
    async def leave_toggle_slash(self, interaction: discord.Interaction, state: Literal["on", "off"]):
        await self.service.set_enabled(interaction.guild_id, state == "on")
        await interaction.response.send_message(embed=await self._confirm(f"Leave system sekarang **{state.upper()}**."))

    @app_commands.command(name="channel", description="Set channel tujuan leave message.")
    @_manage_guild_slash()
    async def leave_channel_slash(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.service.set_field(interaction.guild_id, "channel_id", str(channel.id))
        await interaction.response.send_message(embed=await self._confirm(f"Channel leave diset ke {channel.mention}."))

    @app_commands.command(name="set", description="Set salah satu bagian teks leave (title, description, dst).")
    @app_commands.describe(field="Bagian yang ingin diubah", value="Isi baru (ketik 'none' untuk mengosongkan jika didukung)")
    @app_commands.choices(field=[
        app_commands.Choice(name="Content (plain text)", value="content"),
        app_commands.Choice(name="Embed Title", value="embed_title"),
        app_commands.Choice(name="Embed Description", value="embed_description"),
        app_commands.Choice(name="Embed Color (hex)", value="embed_color"),
        app_commands.Choice(name="Footer Text", value="embed_footer_text"),
        app_commands.Choice(name="Footer Icon URL", value="embed_footer_icon"),
        app_commands.Choice(name="Thumbnail URL (atau 'avatar')", value="embed_thumbnail"),
        app_commands.Choice(name="Banner/Image URL", value="embed_image"),
        app_commands.Choice(name="Author Name", value="embed_author_name"),
        app_commands.Choice(name="Author Icon URL", value="embed_author_icon"),
    ])
    @_manage_guild_slash()
    async def leave_set_slash(self, interaction: discord.Interaction, field: app_commands.Choice[str], value: str):
        column = field.value
        final_value = None if value.lower() == "none" else value
        if column == "embed_color" and final_value:
            try:
                int(final_value.lstrip("#"), 16)
            except ValueError:
                await interaction.response.send_message(embed=JoyEmbed.error("Format warna tidak valid. Contoh: `#FFD54A`"), ephemeral=True)
                return
        if column == "embed_thumbnail" and final_value and final_value.lower() == "avatar":
            final_value = "{user_avatar}"
        await self.service.set_field(interaction.guild_id, column, final_value)
        await interaction.response.send_message(embed=await self._confirm(f"`{field.name}` berhasil diperbarui."))

    @app_commands.command(name="timestamp", description="Toggle timestamp di embed leave.")
    @_manage_guild_slash()
    async def leave_timestamp_slash(self, interaction: discord.Interaction, state: Literal["on", "off"]):
        await self.service.set_field(interaction.guild_id, "embed_timestamp", int(state == "on"))
        await interaction.response.send_message(embed=await self._confirm(f"Timestamp embed: **{state.upper()}**."))

    @app_commands.command(name="card", description="Toggle leave card (image).")
    @_manage_guild_slash()
    async def leave_card_slash(self, interaction: discord.Interaction, state: Literal["on", "off"]):
        await self.service.set_field(interaction.guild_id, "card_enabled", int(state == "on"))
        await interaction.response.send_message(embed=await self._confirm(f"Leave card: **{state.upper()}**."))

    @app_commands.command(name="cardbackground", description="Set/hapus background custom untuk leave card.")
    async def leave_cardbackground_slash(self, interaction: discord.Interaction, url: str):
        value = None if url.lower() == "none" else url
        await self.service.set_field(interaction.guild_id, "card_background", value)
        await interaction.response.send_message(embed=await self._confirm("Background card diperbarui."))

    @app_commands.command(name="avatarposition", description="Posisi avatar di leave card.")
    @app_commands.choices(position=[app_commands.Choice(name=p, value=p) for p in POSITION_CHOICES])
    @_manage_guild_slash()
    async def leave_avatarposition_slash(self, interaction: discord.Interaction, position: app_commands.Choice[str]):
        await self.service.set_field(interaction.guild_id, "card_avatar_position", position.value)
        await interaction.response.send_message(embed=await self._confirm(f"Posisi avatar: **{position.value}**."))

    @app_commands.command(name="textposition", description="Posisi teks di leave card.")
    @app_commands.choices(position=[app_commands.Choice(name=p, value=p) for p in TEXT_POSITION_CHOICES])
    @_manage_guild_slash()
    async def leave_textposition_slash(self, interaction: discord.Interaction, position: app_commands.Choice[str]):
        await self.service.set_field(interaction.guild_id, "card_text_position", position.value)
        await interaction.response.send_message(embed=await self._confirm(f"Posisi teks: **{position.value}**."))

    @app_commands.command(name="button", description="Tambah button link di pesan leave.")
    @_manage_guild_slash()
    async def leave_button_slash(self, interaction: discord.Interaction, label: str, url: str):
        await self.service.set_field(interaction.guild_id, "button_label", label)
        await self.service.set_field(interaction.guild_id, "button_url", url)
        await interaction.response.send_message(embed=await self._confirm(f"Button `{label}` ditambahkan."))

    @app_commands.command(name="removebutton", description="Hapus button dari pesan leave.")
    @_manage_guild_slash()
    async def leave_removebutton_slash(self, interaction: discord.Interaction):
        await self.service.set_field(interaction.guild_id, "button_label", None)
        await self.service.set_field(interaction.guild_id, "button_url", None)
        await interaction.response.send_message(embed=await self._confirm("Button leave dihapus."))

    @app_commands.command(name="test", description="Kirim contoh preview leave message di channel ini.")
    @_manage_guild_slash()
    async def leave_test_slash(self, interaction: discord.Interaction):
        greeting = await self.service.get(interaction.guild_id)
        await interaction.response.defer()
        message = await send_greeting_message(interaction.channel, greeting, interaction.user, interaction.guild, kind="leave")
        if message is None:
            await interaction.followup.send(embed=JoyEmbed.warning("Tidak ada konten yang dikonfigurasi."))
        else:
            await interaction.followup.send(embed=JoyEmbed.success("Preview terkirim di atas."), ephemeral=True)

    @app_commands.command(name="reset", description="Reset seluruh konfigurasi leave ke default.")
    @_manage_guild_slash()
    async def leave_reset_slash(self, interaction: discord.Interaction):
        await self.service.reset(interaction.guild_id)
        await interaction.response.send_message(embed=await self._confirm("Konfigurasi leave dikembalikan ke default."))

    @app_commands.command(name="variables", description="Menampilkan daftar custom variable yang tersedia.")
    async def leave_variables_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=JoyEmbed.info(VARIABLES_HELP, title=f"{emoji.info} Custom Variables"), ephemeral=True)


async def setup(bot: JoyUniverse):
    await bot.add_cog(Leave(bot))
