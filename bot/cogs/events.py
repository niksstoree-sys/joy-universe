"""
Cog Event System untuk JOY UNIVERSE (Stage 3).

Owner/Admin bisa membuat event terjadwal (One Time, Daily, Weekly, Monthly)
lengkap dengan role ping, reminder, banner, thumbnail, dan embed custom.
Scheduler berjalan otomatis di background (tasks.loop) dan mengirim embed
begitu waktunya tiba, lalu menjadwalkan ulang kalau repeat aktif.
"""

from __future__ import annotations

import logging
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.core.bot import JoyUniverse
from bot.core.config import config as bot_config
from bot.models.event import EventRecord
from bot.services.event_service import EventService
from bot.utils.datetime_utils import (
    REPEAT_LABELS,
    compute_next_occurrence,
    db_string_to_utc,
    format_discord_timestamp,
    format_for_display,
    parse_local_to_utc,
    utc_to_db_string,
)
from bot.utils.embeds import JoyEmbed
from bot.utils.emojis import emoji

logger = logging.getLogger("joyuniverse.cogs.events")

REPEAT_CHOICES = ["once", "daily", "weekly", "monthly"]


def _manage_guild_prefix():
    return commands.has_permissions(manage_guild=True)


def _manage_guild_slash():
    return app_commands.checks.has_permissions(manage_guild=True)


class Event(commands.GroupCog, name="event"):
    """Slash commands otomatis ter-grup di bawah `/event`."""

    def __init__(self, bot: JoyUniverse):
        self.bot = bot
        self.service = EventService(bot.db)
        self.scheduler_loop.start()

    def cog_unload(self) -> None:
        self.scheduler_loop.cancel()

    # ================= SCHEDULER =================

    @tasks.loop(seconds=30)
    async def scheduler_loop(self):
        try:
            for event in await self.service.get_due_events():
                await self._fire_event(event)
            for event in await self.service.get_due_reminders():
                await self._fire_reminder(event)
        except Exception:
            logger.exception("Error di event scheduler loop")

    @scheduler_loop.before_loop
    async def before_scheduler(self):
        await self.bot.wait_until_ready()

    async def _fire_event(self, event: EventRecord) -> None:
        channel = self.bot.get_channel(int(event.channel_id))
        if channel is not None:
            embed = self._build_event_embed(event)
            content = f"<@&{event.role_ping_id}>" if event.role_ping_id else None
            try:
                await channel.send(content=content, embed=embed)
            except discord.HTTPException:
                logger.exception("Gagal mengirim event '%s' ke channel %s", event.name, event.channel_id)
        else:
            logger.warning("Channel event '%s' (ID %s) tidak ditemukan.", event.name, event.channel_id)

        next_run = compute_next_occurrence(db_string_to_utc(event.run_at), event.repeat_type)
        await self.service.advance_or_deactivate(event.id, next_run)

    async def _fire_reminder(self, event: EventRecord) -> None:
        channel = self.bot.get_channel(int(event.channel_id))
        if channel is not None:
            embed = JoyEmbed.warning(
                f"Event **{event.name}** akan dimulai {format_discord_timestamp(event.run_at, 'R')}!",
                title=f"{emoji.warning} Reminder Event",
            )
            content = f"<@&{event.role_ping_id}>" if event.role_ping_id else None
            try:
                await channel.send(content=content, embed=embed)
            except discord.HTTPException:
                logger.exception("Gagal mengirim reminder event '%s'", event.name)
        await self.service.mark_reminder_sent(event.id)

    def _build_event_embed(self, event: EventRecord) -> discord.Embed:
        color = int(event.embed_color.lstrip("#"), 16) if event.embed_color else bot_config.default_color
        embed = JoyEmbed(title=event.name, description=event.description, color=color)
        if event.thumbnail_url:
            embed.set_thumbnail(url=event.thumbnail_url)
        if event.banner_url:
            embed.set_image(url=event.banner_url)
        embed.set_footer(text=f"Event System · Repeat: {REPEAT_LABELS.get(event.repeat_type, event.repeat_type)}")
        return embed

    async def _confirm(self, description: str) -> discord.Embed:
        return JoyEmbed.success(description)

    def _build_info_embed(self, event: EventRecord) -> discord.Embed:
        embed = JoyEmbed.info(
            f"**Deskripsi:** {event.description or '-'}\n"
            f"**Channel:** <#{event.channel_id}>\n"
            f"**Role Ping:** {f'<@&{event.role_ping_id}>' if event.role_ping_id else '-'}\n"
            f"**Jadwal:** {format_discord_timestamp(event.run_at)} ({format_discord_timestamp(event.run_at, 'R')})\n"
            f"**Repeat:** {REPEAT_LABELS.get(event.repeat_type, event.repeat_type)}\n"
            f"**Reminder:** {f'{event.reminder_minutes} menit sebelum' if event.reminder_minutes else '-'}\n"
            f"**Timezone dibuat:** {event.timezone}",
            title=f"{emoji.info} Event #{event.id} — {event.name}",
        )
        if event.thumbnail_url:
            embed.set_thumbnail(url=event.thumbnail_url)
        if event.banner_url:
            embed.set_image(url=event.banner_url)
        return embed

    # ================= PREFIX COMMAND GROUP =================

    @commands.group(name="event", invoke_without_command=True)
    @commands.guild_only()
    async def event_group(self, ctx: commands.Context):
        """Menampilkan daftar event aktif. Gunakan `!help event` untuk subcommand lengkap."""
        await self._send_list(ctx)

    @event_group.command(name="create")
    @_manage_guild_prefix()
    async def event_create(
        self,
        ctx: commands.Context,
        name: str,
        date: str,
        time: str,
        channel: discord.TextChannel,
        timezone_name: str = "WIB",
    ):
        """Contoh: !event create "Malam Kuis" 2026-07-10 19:00 #event WIB"""
        try:
            run_at_utc = parse_local_to_utc(date, time, timezone_name)
        except ValueError as e:
            await ctx.send(embed=JoyEmbed.error(str(e)))
            return

        event_id = await self.service.create(
            guild_id=ctx.guild.id,
            name=name,
            channel_id=channel.id,
            run_at_utc=run_at_utc,
            tz_name=timezone_name,
            created_by=ctx.author.id,
        )
        await ctx.send(embed=await self._confirm(
            f"Event **{name}** (ID `{event_id}`) berhasil dibuat, dijadwalkan {format_discord_timestamp(utc_to_db_string(run_at_utc))}."
        ))

    @event_group.command(name="description")
    @_manage_guild_prefix()
    async def event_description(self, ctx: commands.Context, event_id: int, *, text: str):
        """Atur deskripsi event."""
        ok = await self.service.set_field(event_id, ctx.guild.id, "description", text)
        await ctx.send(embed=await self._confirm("Deskripsi event diperbarui.") if ok else JoyEmbed.error("Event tidak ditemukan."))

    @event_group.command(name="repeat")
    @_manage_guild_prefix()
    async def event_repeat(self, ctx: commands.Context, event_id: int, repeat_type: str):
        """Atur pengulangan event (sekali/harian/mingguan/bulanan)."""
        repeat_type = repeat_type.lower()
        if repeat_type not in REPEAT_CHOICES:
            await ctx.send(embed=JoyEmbed.error(f"Pilihan: {', '.join(REPEAT_CHOICES)}"))
            return
        ok = await self.service.set_field(event_id, ctx.guild.id, "repeat_type", repeat_type)
        await ctx.send(embed=await self._confirm(f"Repeat diset ke **{REPEAT_LABELS[repeat_type]}**.") if ok else JoyEmbed.error("Event tidak ditemukan."))

    @event_group.command(name="roleping")
    @_manage_guild_prefix()
    async def event_roleping(self, ctx: commands.Context, event_id: int, role: discord.Role | None = None):
        """Atur role yang di-mention saat event dimulai."""
        ok = await self.service.set_field(event_id, ctx.guild.id, "role_ping_id", str(role.id) if role else None)
        await ctx.send(embed=await self._confirm("Role ping diperbarui.") if ok else JoyEmbed.error("Event tidak ditemukan."))

    @event_group.command(name="reminder")
    @_manage_guild_prefix()
    async def event_reminder(self, ctx: commands.Context, event_id: int, minutes: int | None = None):
        """Atur reminder sebelum event dimulai (dalam menit)."""
        ok = await self.service.set_field(event_id, ctx.guild.id, "reminder_minutes", minutes)
        await ctx.send(embed=await self._confirm("Reminder diperbarui.") if ok else JoyEmbed.error("Event tidak ditemukan."))

    @event_group.command(name="banner")
    @_manage_guild_prefix()
    async def event_banner(self, ctx: commands.Context, event_id: int, url: str):
        """Atur banner event."""
        value = None if url.lower() == "none" else url
        ok = await self.service.set_field(event_id, ctx.guild.id, "banner_url", value)
        await ctx.send(embed=await self._confirm("Banner event diperbarui.") if ok else JoyEmbed.error("Event tidak ditemukan."))

    @event_group.command(name="thumbnail")
    @_manage_guild_prefix()
    async def event_thumbnail(self, ctx: commands.Context, event_id: int, url: str):
        """Atur thumbnail event."""
        value = None if url.lower() == "none" else url
        ok = await self.service.set_field(event_id, ctx.guild.id, "thumbnail_url", value)
        await ctx.send(embed=await self._confirm("Thumbnail event diperbarui.") if ok else JoyEmbed.error("Event tidak ditemukan."))

    @event_group.command(name="color")
    @_manage_guild_prefix()
    async def event_color(self, ctx: commands.Context, event_id: int, hex_color: str):
        """Atur warna embed event."""
        try:
            int(hex_color.lstrip("#"), 16)
        except ValueError:
            await ctx.send(embed=JoyEmbed.error("Format warna tidak valid. Contoh: `#FFD54A`"))
            return
        ok = await self.service.set_field(event_id, ctx.guild.id, "embed_color", hex_color)
        await ctx.send(embed=await self._confirm("Warna embed event diperbarui.") if ok else JoyEmbed.error("Event tidak ditemukan."))

    @event_group.command(name="channel")
    @_manage_guild_prefix()
    async def event_channel(self, ctx: commands.Context, event_id: int, channel: discord.TextChannel):
        """Atur channel tujuan pengumuman event."""
        ok = await self.service.set_field(event_id, ctx.guild.id, "channel_id", str(channel.id))
        await ctx.send(embed=await self._confirm(f"Channel event diset ke {channel.mention}.") if ok else JoyEmbed.error("Event tidak ditemukan."))

    @event_group.command(name="reschedule")
    @_manage_guild_prefix()
    async def event_reschedule(self, ctx: commands.Context, event_id: int, date: str, time: str, timezone_name: str = "WIB"):
        """Jadwalkan ulang event ke tanggal/jam baru."""
        try:
            run_at_utc = parse_local_to_utc(date, time, timezone_name)
        except ValueError as e:
            await ctx.send(embed=JoyEmbed.error(str(e)))
            return
        ok = await self.service.reschedule(event_id, ctx.guild.id, run_at_utc, timezone_name)
        await ctx.send(embed=await self._confirm("Jadwal event diperbarui.") if ok else JoyEmbed.error("Event tidak ditemukan."))

    @event_group.command(name="cancel")
    @_manage_guild_prefix()
    async def event_cancel(self, ctx: commands.Context, event_id: int):
        """Batalkan event."""
        ok = await self.service.cancel(event_id, ctx.guild.id)
        await ctx.send(embed=await self._confirm(f"Event #{event_id} dibatalkan.") if ok else JoyEmbed.error("Event tidak ditemukan."))

    @event_group.command(name="list")
    async def event_list(self, ctx: commands.Context):
        """Menampilkan daftar event aktif."""
        await self._send_list(ctx)

    @event_group.command(name="info")
    async def event_info(self, ctx: commands.Context, event_id: int):
        """Menampilkan detail satu event."""
        event = await self.service.get(event_id, ctx.guild.id)
        if event is None:
            await ctx.send(embed=JoyEmbed.error("Event tidak ditemukan."))
            return
        await ctx.send(embed=self._build_info_embed(event))

    @event_group.command(name="countdown")
    async def event_countdown(self, ctx: commands.Context, event_id: int):
        """Menampilkan hitung mundur event."""
        event = await self.service.get(event_id, ctx.guild.id)
        if event is None:
            await ctx.send(embed=JoyEmbed.error("Event tidak ditemukan."))
            return
        await ctx.send(embed=JoyEmbed.info(
            f"Event **{event.name}** akan dimulai {format_discord_timestamp(event.run_at, 'R')}.",
            title=f"{emoji.info} Countdown",
        ))

    async def _send_list(self, ctx: commands.Context):
        events = await self.service.list_active(ctx.guild.id)
        if not events:
            await ctx.send(embed=JoyEmbed.info("Belum ada event aktif di server ini."))
            return
        lines = [
            f"`#{e.id}` **{e.name}** — {format_discord_timestamp(e.run_at, 'R')} · {REPEAT_LABELS.get(e.repeat_type, e.repeat_type)}"
            for e in events
        ]
        await ctx.send(embed=JoyEmbed.info("\n".join(lines), title=f"{emoji.info} Daftar Event Aktif"))

    # ================= SLASH COMMAND (auto grouped: /event ...) =================

    @app_commands.command(name="create", description="Membuat event baru.")
    @app_commands.describe(
        name="Nama event",
        date="Tanggal (YYYY-MM-DD)",
        time="Jam (HH:MM)",
        channel="Channel tujuan pengumuman",
        timezone_name="Timezone, contoh: WIB, WITA, WIT (default WIB)",
        repeat="Pengulangan event",
        role_ping="Role yang di-mention saat event dimulai",
        reminder_minutes="Kirim reminder berapa menit sebelum event",
        description="Deskripsi event",
        banner_url="URL banner (gambar besar)",
        thumbnail_url="URL thumbnail",
        embed_color="Warna embed (hex, contoh #FFD54A)",
    )
    @app_commands.choices(repeat=[app_commands.Choice(name=REPEAT_LABELS[r], value=r) for r in REPEAT_CHOICES])
    @_manage_guild_slash()
    async def event_create_slash(
        self,
        interaction: discord.Interaction,
        name: str,
        date: str,
        time: str,
        channel: discord.TextChannel,
        timezone_name: str = "WIB",
        repeat: app_commands.Choice[str] | None = None,
        role_ping: discord.Role | None = None,
        reminder_minutes: int | None = None,
        description: str | None = None,
        banner_url: str | None = None,
        thumbnail_url: str | None = None,
        embed_color: str | None = None,
    ):
        try:
            run_at_utc = parse_local_to_utc(date, time, timezone_name)
        except ValueError as e:
            await interaction.response.send_message(embed=JoyEmbed.error(str(e)), ephemeral=True)
            return

        if embed_color:
            try:
                int(embed_color.lstrip("#"), 16)
            except ValueError:
                await interaction.response.send_message(embed=JoyEmbed.error("Format warna tidak valid."), ephemeral=True)
                return

        event_id = await self.service.create(
            guild_id=interaction.guild_id,
            name=name,
            channel_id=channel.id,
            run_at_utc=run_at_utc,
            tz_name=timezone_name,
            created_by=interaction.user.id,
            description=description,
            role_ping_id=role_ping.id if role_ping else None,
            repeat_type=repeat.value if repeat else "once",
            reminder_minutes=reminder_minutes,
            banner_url=banner_url,
            thumbnail_url=thumbnail_url,
            embed_color=embed_color,
        )
        await interaction.response.send_message(embed=await self._confirm(
            f"Event **{name}** (ID `{event_id}`) berhasil dibuat di {channel.mention}."
        ))

    @app_commands.command(name="list", description="Menampilkan daftar event aktif.")
    async def event_list_slash(self, interaction: discord.Interaction):
        events = await self.service.list_active(interaction.guild_id)
        if not events:
            await interaction.response.send_message(embed=JoyEmbed.info("Belum ada event aktif di server ini."))
            return
        lines = [
            f"`#{e.id}` **{e.name}** — {format_discord_timestamp(e.run_at, 'R')} · {REPEAT_LABELS.get(e.repeat_type, e.repeat_type)}"
            for e in events
        ]
        await interaction.response.send_message(embed=JoyEmbed.info("\n".join(lines), title=f"{emoji.info} Daftar Event Aktif"))

    @app_commands.command(name="info", description="Menampilkan detail satu event.")
    async def event_info_slash(self, interaction: discord.Interaction, event_id: int):
        event = await self.service.get(event_id, interaction.guild_id)
        if event is None:
            await interaction.response.send_message(embed=JoyEmbed.error("Event tidak ditemukan."), ephemeral=True)
            return
        await interaction.response.send_message(embed=self._build_info_embed(event))

    @app_commands.command(name="cancel", description="Membatalkan event.")
    @_manage_guild_slash()
    async def event_cancel_slash(self, interaction: discord.Interaction, event_id: int):
        ok = await self.service.cancel(event_id, interaction.guild_id)
        await interaction.response.send_message(
            embed=await self._confirm(f"Event #{event_id} dibatalkan.") if ok else JoyEmbed.error("Event tidak ditemukan.")
        )

    @app_commands.command(name="set", description="Edit salah satu bagian event (deskripsi, warna, banner, dst).")
    @app_commands.choices(field=[
        app_commands.Choice(name="Deskripsi", value="description"),
        app_commands.Choice(name="Warna Embed (hex)", value="embed_color"),
        app_commands.Choice(name="Banner URL", value="banner_url"),
        app_commands.Choice(name="Thumbnail URL", value="thumbnail_url"),
    ])
    @_manage_guild_slash()
    async def event_set_slash(self, interaction: discord.Interaction, event_id: int, field: app_commands.Choice[str], value: str):
        final_value = None if value.lower() == "none" else value
        if field.value == "embed_color" and final_value:
            try:
                int(final_value.lstrip("#"), 16)
            except ValueError:
                await interaction.response.send_message(embed=JoyEmbed.error("Format warna tidak valid."), ephemeral=True)
                return
        ok = await self.service.set_field(event_id, interaction.guild_id, field.value, final_value)
        await interaction.response.send_message(
            embed=await self._confirm(f"`{field.name}` berhasil diperbarui.") if ok else JoyEmbed.error("Event tidak ditemukan.")
        )

    @app_commands.command(name="repeat", description="Ubah pengulangan event.")
    @app_commands.choices(repeat=[app_commands.Choice(name=REPEAT_LABELS[r], value=r) for r in REPEAT_CHOICES])
    @_manage_guild_slash()
    async def event_repeat_slash(self, interaction: discord.Interaction, event_id: int, repeat: app_commands.Choice[str]):
        ok = await self.service.set_field(event_id, interaction.guild_id, "repeat_type", repeat.value)
        await interaction.response.send_message(
            embed=await self._confirm(f"Repeat diset ke **{repeat.name}**.") if ok else JoyEmbed.error("Event tidak ditemukan.")
        )

    @app_commands.command(name="roleping", description="Set/hapus role yang di-ping saat event dimulai.")
    @_manage_guild_slash()
    async def event_roleping_slash(self, interaction: discord.Interaction, event_id: int, role: discord.Role | None = None):
        ok = await self.service.set_field(event_id, interaction.guild_id, "role_ping_id", str(role.id) if role else None)
        await interaction.response.send_message(
            embed=await self._confirm("Role ping diperbarui.") if ok else JoyEmbed.error("Event tidak ditemukan.")
        )

    @app_commands.command(name="reminder", description="Set/hapus reminder (menit sebelum event).")
    @_manage_guild_slash()
    async def event_reminder_slash(self, interaction: discord.Interaction, event_id: int, minutes: int | None = None):
        ok = await self.service.set_field(event_id, interaction.guild_id, "reminder_minutes", minutes)
        await interaction.response.send_message(
            embed=await self._confirm("Reminder diperbarui.") if ok else JoyEmbed.error("Event tidak ditemukan.")
        )

    @app_commands.command(name="reschedule", description="Jadwalkan ulang event ke tanggal/jam baru.")
    @_manage_guild_slash()
    async def event_reschedule_slash(self, interaction: discord.Interaction, event_id: int, date: str, time: str, timezone_name: str = "WIB"):
        try:
            run_at_utc = parse_local_to_utc(date, time, timezone_name)
        except ValueError as e:
            await interaction.response.send_message(embed=JoyEmbed.error(str(e)), ephemeral=True)
            return
        ok = await self.service.reschedule(event_id, interaction.guild_id, run_at_utc, timezone_name)
        await interaction.response.send_message(
            embed=await self._confirm("Jadwal event diperbarui.") if ok else JoyEmbed.error("Event tidak ditemukan.")
        )

    @app_commands.command(name="countdown", description="Menampilkan hitung mundur event.")
    async def event_countdown_slash(self, interaction: discord.Interaction, event_id: int):
        event = await self.service.get(event_id, interaction.guild_id)
        if event is None:
            await interaction.response.send_message(embed=JoyEmbed.error("Event tidak ditemukan."), ephemeral=True)
            return
        await interaction.response.send_message(embed=JoyEmbed.info(
            f"Event **{event.name}** akan dimulai {format_discord_timestamp(event.run_at, 'R')}.",
            title=f"{emoji.info} Countdown",
        ))


async def setup(bot: JoyUniverse):
    await bot.add_cog(Event(bot))
