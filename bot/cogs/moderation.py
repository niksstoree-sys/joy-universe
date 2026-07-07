"""
Cog Moderation untuk JOY UNIVERSE (Stage 7).

Mencakup semua command moderasi manual (Ban, Soft Ban, Kick, Mute, Timeout,
Warn, Slowmode, Lock/Unlock, Purge, Unban, Nickname, Role, Voice Moderation)
plus Moderation Log otomatis untuk berbagai aktivitas server.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.bot import JoyUniverse
from bot.services.guild_config_service import GuildConfigService
from bot.services.moderation_service import ModerationService
from bot.utils.duration_parser import format_duration, parse_duration
from bot.utils.embeds import JoyEmbed
from bot.utils.emojis import emoji

logger = logging.getLogger("joyuniverse.cogs.moderation")


class Moderation(commands.Cog):
    """Prefix: `!ban`, `!kick`, `!mute`, dst. Slash: `/ban`, `/kick`, `/mute`, dst."""

    def __init__(self, bot: JoyUniverse):
        self.bot = bot
        self.mod_service = ModerationService(bot.db)
        self.guild_config_service = GuildConfigService(bot.db)

    # ================= HELPERS =================

    async def _send_log(self, guild: discord.Guild, category: str, embed: discord.Embed) -> None:
        try:
            log_config = await self.mod_service.get_log_config(guild.id)
            if not getattr(log_config, category, True):
                return
            guild_config = await self.guild_config_service.get(guild.id)
            if not guild_config.mod_log_channel:
                return
            channel = guild.get_channel(int(guild_config.mod_log_channel))
            if channel is None:
                return
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass
        except Exception:
            logger.exception("Gagal mengirim moderation log di guild %s", guild.id)

    async def _get_or_create_mute_role(self, guild: discord.Guild) -> discord.Role:
        config = await self.guild_config_service.get(guild.id)
        if config.mute_role_id:
            role = guild.get_role(int(config.mute_role_id))
            if role is not None:
                return role

        role = await guild.create_role(
            name="Muted", color=discord.Color.dark_grey(), reason="Auto-created Muted role"
        )
        for channel in guild.channels:
            try:
                overwrite = channel.overwrites_for(role)
                overwrite.send_messages = False
                overwrite.add_reactions = False
                overwrite.speak = False
                overwrite.stream = False
                await channel.set_permissions(role, overwrite=overwrite, reason="Setup Muted role")
            except (discord.Forbidden, discord.HTTPException):
                continue

        await self.guild_config_service.set_mute_role_id(guild.id, role.id)
        return role

    async def _confirm(self, text: str) -> discord.Embed:
        return JoyEmbed.success(text)

    # ================= BAN / SOFTBAN / KICK / UNBAN =================

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban_prefix(self, ctx: commands.Context, member: discord.Member, *, reason: str = "Tidak ada alasan"):
        """Ban member dari server."""
        await self._do_ban(ctx.guild, member, ctx.author, reason)
        await ctx.send(embed=await self._confirm(f"{member.mention} telah di-ban. Alasan: {reason}"))

    @app_commands.command(name="ban", description="Ban member dari server.")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Tidak ada alasan"):
        await self._do_ban(interaction.guild, member, interaction.user, reason)
        await interaction.response.send_message(embed=await self._confirm(f"{member.mention} telah di-ban. Alasan: {reason}"))

    async def _do_ban(self, guild: discord.Guild, member: discord.Member, moderator, reason: str) -> None:
        await member.ban(reason=reason, delete_message_seconds=86400)
        await self.mod_service.add_history(guild.id, member.id, moderator.id, "ban", reason)
        await self._send_log(guild, "log_moderation_action", JoyEmbed.error(
            f"**User:** {member.mention} (`{member.id}`)\n**Moderator:** {moderator.mention}\n**Alasan:** {reason}",
            title=f"{emoji.ban} Member Di-ban",
        ))

    @commands.command(name="softban")
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def softban_prefix(self, ctx: commands.Context, member: discord.Member, *, reason: str = "Tidak ada alasan"):
        """Softban member (hapus pesan lalu langsung unban)."""
        await self._do_softban(ctx.guild, member, ctx.author, reason)
        await ctx.send(embed=await self._confirm(f"{member.mention} di-softban (pesan dibersihkan, langsung bisa join lagi)."))

    @app_commands.command(name="softban", description="Softban: hapus pesan member lalu langsung unban.")
    @app_commands.checks.has_permissions(ban_members=True)
    async def softban_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Tidak ada alasan"):
        await self._do_softban(interaction.guild, member, interaction.user, reason)
        await interaction.response.send_message(embed=await self._confirm(f"{member.mention} di-softban."))

    async def _do_softban(self, guild: discord.Guild, member: discord.Member, moderator, reason: str) -> None:
        await member.ban(reason=f"Softban: {reason}", delete_message_seconds=86400)
        await guild.unban(member, reason="Softban - auto unban")
        await self.mod_service.add_history(guild.id, member.id, moderator.id, "softban", reason)
        await self._send_log(guild, "log_moderation_action", JoyEmbed.warning(
            f"**User:** {member.mention} (`{member.id}`)\n**Moderator:** {moderator.mention}\n**Alasan:** {reason}",
            title=f"{emoji.ban} Member Di-softban",
        ))

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick_prefix(self, ctx: commands.Context, member: discord.Member, *, reason: str = "Tidak ada alasan"):
        """Kick member dari server."""
        await self._do_kick(ctx.guild, member, ctx.author, reason)
        await ctx.send(embed=await self._confirm(f"{member.mention} telah di-kick. Alasan: {reason}"))

    @app_commands.command(name="kick", description="Kick member dari server.")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Tidak ada alasan"):
        await self._do_kick(interaction.guild, member, interaction.user, reason)
        await interaction.response.send_message(embed=await self._confirm(f"{member.mention} telah di-kick. Alasan: {reason}"))

    async def _do_kick(self, guild: discord.Guild, member: discord.Member, moderator, reason: str) -> None:
        await member.kick(reason=reason)
        await self.mod_service.add_history(guild.id, member.id, moderator.id, "kick", reason)
        await self._send_log(guild, "log_moderation_action", JoyEmbed.warning(
            f"**User:** {member.mention} (`{member.id}`)\n**Moderator:** {moderator.mention}\n**Alasan:** {reason}",
            title=f"{emoji.kick} Member Di-kick",
        ))

    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def unban_prefix(self, ctx: commands.Context, user_id: int, *, reason: str = "Tidak ada alasan"):
        """Unban user berdasarkan User ID."""
        await self._do_unban(ctx.guild, user_id, ctx.author, reason, ctx)

    @app_commands.command(name="unban", description="Unban user berdasarkan User ID.")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban_slash(self, interaction: discord.Interaction, user_id: str, reason: str = "Tidak ada alasan"):
        await self._do_unban(interaction.guild, int(user_id), interaction.user, reason, interaction)

    async def _do_unban(self, guild: discord.Guild, user_id: int, moderator, reason: str, ctx_or_interaction) -> None:
        user = discord.Object(id=user_id)
        try:
            await guild.unban(user, reason=reason)
        except discord.NotFound:
            embed = JoyEmbed.error("User tidak ditemukan di ban list.")
            await self._reply(ctx_or_interaction, embed)
            return
        await self.mod_service.add_history(guild.id, user_id, moderator.id, "unban", reason)
        await self._send_log(guild, "log_moderation_action", JoyEmbed.success(
            f"**User ID:** `{user_id}`\n**Moderator:** {moderator.mention}\n**Alasan:** {reason}",
            title=f"{emoji.success} User Di-unban",
        ))
        await self._reply(ctx_or_interaction, JoyEmbed.success(f"User `{user_id}` telah di-unban."))

    async def _reply(self, ctx_or_interaction, embed: discord.Embed) -> None:
        if isinstance(ctx_or_interaction, discord.Interaction):
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(embed=embed)
            else:
                await ctx_or_interaction.response.send_message(embed=embed)
        else:
            await ctx_or_interaction.send(embed=embed)

    # ================= MUTE (role-based) =================

    @commands.command(name="mute")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def mute_prefix(self, ctx: commands.Context, member: discord.Member, *, reason: str = "Tidak ada alasan"):
        """Mute member (role-based, permanen sampai di-unmute)."""
        role = await self._get_or_create_mute_role(ctx.guild)
        await member.add_roles(role, reason=reason)
        await self.mod_service.add_history(ctx.guild.id, member.id, ctx.author.id, "mute", reason)
        await self._send_log(ctx.guild, "log_moderation_action", JoyEmbed.warning(
            f"**User:** {member.mention}\n**Moderator:** {ctx.author.mention}\n**Alasan:** {reason}",
            title=f"{emoji.mute} Member Di-mute",
        ))
        await ctx.send(embed=await self._confirm(f"{member.mention} telah di-mute."))

    @app_commands.command(name="mute", description="Mute member (role-based, permanen sampai di-unmute).")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Tidak ada alasan"):
        role = await self._get_or_create_mute_role(interaction.guild)
        await member.add_roles(role, reason=reason)
        await self.mod_service.add_history(interaction.guild_id, member.id, interaction.user.id, "mute", reason)
        await self._send_log(interaction.guild, "log_moderation_action", JoyEmbed.warning(
            f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Alasan:** {reason}",
            title=f"{emoji.mute} Member Di-mute",
        ))
        await interaction.response.send_message(embed=await self._confirm(f"{member.mention} telah di-mute."))

    @commands.command(name="unmute")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def unmute_prefix(self, ctx: commands.Context, member: discord.Member):
        """Unmute member."""
        config = await self.guild_config_service.get(ctx.guild.id)
        if config.mute_role_id:
            role = ctx.guild.get_role(int(config.mute_role_id))
            if role and role in member.roles:
                await member.remove_roles(role, reason="Unmute")
        await self.mod_service.add_history(ctx.guild.id, member.id, ctx.author.id, "unmute")
        await ctx.send(embed=await self._confirm(f"{member.mention} telah di-unmute."))

    @app_commands.command(name="unmute", description="Unmute member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute_slash(self, interaction: discord.Interaction, member: discord.Member):
        config = await self.guild_config_service.get(interaction.guild_id)
        if config.mute_role_id:
            role = interaction.guild.get_role(int(config.mute_role_id))
            if role and role in member.roles:
                await member.remove_roles(role, reason="Unmute")
        await self.mod_service.add_history(interaction.guild_id, member.id, interaction.user.id, "unmute")
        await interaction.response.send_message(embed=await self._confirm(f"{member.mention} telah di-unmute."))

    # ================= TIMEOUT (native Discord) =================

    @commands.command(name="timeout")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def timeout_prefix(self, ctx: commands.Context, member: discord.Member, duration: str, *, reason: str = "Tidak ada alasan"):
        """Timeout member. Contoh durasi: 10m, 1h, 2d."""
        try:
            seconds = parse_duration(duration)
        except ValueError as e:
            await ctx.send(embed=JoyEmbed.error(str(e)))
            return
        await self._do_timeout(ctx.guild, member, ctx.author, seconds, reason)
        await ctx.send(embed=await self._confirm(f"{member.mention} di-timeout selama **{format_duration(seconds)}**."))

    @app_commands.command(name="timeout", description="Timeout member. Contoh durasi: 10m, 1h, 2d.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout_slash(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "Tidak ada alasan"):
        try:
            seconds = parse_duration(duration)
        except ValueError as e:
            await interaction.response.send_message(embed=JoyEmbed.error(str(e)), ephemeral=True)
            return
        await self._do_timeout(interaction.guild, member, interaction.user, seconds, reason)
        await interaction.response.send_message(embed=await self._confirm(f"{member.mention} di-timeout selama **{format_duration(seconds)}**."))

    async def _do_timeout(self, guild: discord.Guild, member: discord.Member, moderator, seconds: int, reason: str) -> None:
        await member.timeout(discord.utils.utcnow() + timedelta(seconds=seconds), reason=reason)
        await self.mod_service.add_history(guild.id, member.id, moderator.id, "timeout", reason, seconds)
        await self._send_log(guild, "log_moderation_action", JoyEmbed.warning(
            f"**User:** {member.mention}\n**Moderator:** {moderator.mention}\n**Durasi:** {format_duration(seconds)}\n**Alasan:** {reason}",
            title=f"{emoji.warning} Member Di-timeout",
        ))

    @commands.command(name="untimeout")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def untimeout_prefix(self, ctx: commands.Context, member: discord.Member):
        """Cabut timeout dari member."""
        await member.timeout(None, reason="Untimeout")
        await self.mod_service.add_history(ctx.guild.id, member.id, ctx.author.id, "untimeout")
        await ctx.send(embed=await self._confirm(f"Timeout {member.mention} telah dicabut."))

    @app_commands.command(name="untimeout", description="Cabut timeout member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout_slash(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None, reason="Untimeout")
        await self.mod_service.add_history(interaction.guild_id, member.id, interaction.user.id, "untimeout")
        await interaction.response.send_message(embed=await self._confirm(f"Timeout {member.mention} telah dicabut."))

    # ================= WARN =================

    @commands.command(name="warn")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def warn_prefix(self, ctx: commands.Context, member: discord.Member, *, reason: str):
        """Beri warning ke member."""
        warning_id = await self.mod_service.add_warning(ctx.guild.id, member.id, ctx.author.id, reason)
        await self.mod_service.add_history(ctx.guild.id, member.id, ctx.author.id, "warn", reason)
        await self._send_log(ctx.guild, "log_moderation_action", JoyEmbed.warning(
            f"**User:** {member.mention}\n**Moderator:** {ctx.author.mention}\n**Alasan:** {reason}",
            title=f"{emoji.warn} Member Diberi Warning (#{warning_id})",
        ))
        await ctx.send(embed=await self._confirm(f"{member.mention} diberi warning (`#{warning_id}`). Alasan: {reason}"))

    @app_commands.command(name="warn", description="Beri warning ke member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        warning_id = await self.mod_service.add_warning(interaction.guild_id, member.id, interaction.user.id, reason)
        await self.mod_service.add_history(interaction.guild_id, member.id, interaction.user.id, "warn", reason)
        await self._send_log(interaction.guild, "log_moderation_action", JoyEmbed.warning(
            f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Alasan:** {reason}",
            title=f"{emoji.warn} Member Diberi Warning (#{warning_id})",
        ))
        await interaction.response.send_message(embed=await self._confirm(f"{member.mention} diberi warning (`#{warning_id}`). Alasan: {reason}"))

    @commands.command(name="warnings")
    @commands.guild_only()
    async def warnings_prefix(self, ctx: commands.Context, member: discord.Member):
        """Menampilkan daftar warning member."""
        await self._send_warnings(ctx, member)

    @app_commands.command(name="warnings", description="Menampilkan daftar warning member.")
    async def warnings_slash(self, interaction: discord.Interaction, member: discord.Member):
        await self._send_warnings(interaction, member)

    async def _send_warnings(self, ctx_or_interaction, member: discord.Member) -> None:
        guild_id = ctx_or_interaction.guild.id if isinstance(ctx_or_interaction, commands.Context) else ctx_or_interaction.guild_id
        warnings = await self.mod_service.get_warnings(guild_id, member.id)
        if not warnings:
            embed = JoyEmbed.info(f"{member.mention} tidak punya warning aktif.")
        else:
            lines = [f"`#{w.id}` {w.reason} — oleh <@{w.moderator_id}> ({w.created_at})" for w in warnings]
            embed = JoyEmbed.info("\n".join(lines), title=f"{emoji.warn} Warnings — {member.display_name}")
        await self._reply(ctx_or_interaction, embed)

    @commands.command(name="removewarn")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def removewarn_prefix(self, ctx: commands.Context, warning_id: int):
        """Hapus satu warning berdasarkan ID."""
        ok = await self.mod_service.remove_warning(warning_id, ctx.guild.id)
        await ctx.send(embed=await self._confirm(f"Warning `#{warning_id}` dihapus.") if ok else JoyEmbed.error("Warning tidak ditemukan."))

    @app_commands.command(name="removewarn", description="Hapus satu warning berdasarkan ID.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def removewarn_slash(self, interaction: discord.Interaction, warning_id: int):
        ok = await self.mod_service.remove_warning(warning_id, interaction.guild_id)
        await interaction.response.send_message(embed=await self._confirm(f"Warning `#{warning_id}` dihapus.") if ok else JoyEmbed.error("Warning tidak ditemukan."))

    @commands.command(name="clearwarnings")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def clearwarnings_prefix(self, ctx: commands.Context, member: discord.Member):
        """Hapus semua warning member."""
        count = await self.mod_service.clear_warnings(ctx.guild.id, member.id)
        await ctx.send(embed=await self._confirm(f"{count} warning {member.mention} telah dihapus."))

    @app_commands.command(name="clearwarnings", description="Hapus semua warning member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def clearwarnings_slash(self, interaction: discord.Interaction, member: discord.Member):
        count = await self.mod_service.clear_warnings(interaction.guild_id, member.id)
        await interaction.response.send_message(embed=await self._confirm(f"{count} warning {member.mention} telah dihapus."))

    # ================= HISTORY =================

    @commands.command(name="history")
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def history_prefix(self, ctx: commands.Context, member: discord.Member):
        """Menampilkan riwayat moderasi member."""
        await self._send_history(ctx, member)

    @app_commands.command(name="history", description="Menampilkan riwayat moderasi member.")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def history_slash(self, interaction: discord.Interaction, member: discord.Member):
        await self._send_history(interaction, member)

    async def _send_history(self, ctx_or_interaction, member: discord.Member) -> None:
        guild_id = ctx_or_interaction.guild.id if isinstance(ctx_or_interaction, commands.Context) else ctx_or_interaction.guild_id
        entries = await self.mod_service.get_history(guild_id, member.id)
        if not entries:
            embed = JoyEmbed.info(f"{member.mention} belum punya riwayat moderasi.")
        else:
            lines = []
            for e in entries:
                line = f"`{e.created_at}` **{e.action.upper()}** oleh <@{e.moderator_id}>"
                if e.reason:
                    line += f" — {e.reason}"
                if e.duration_seconds:
                    line += f" ({format_duration(e.duration_seconds)})"
                lines.append(line)
            embed = JoyEmbed.info("\n".join(lines), title=f"{emoji.info} Riwayat Moderasi — {member.display_name}")
        await self._reply(ctx_or_interaction, embed)

    # ================= SLOWMODE / LOCK / UNLOCK / PURGE =================

    @commands.command(name="slowmode")
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def slowmode_prefix(self, ctx: commands.Context, seconds: int, channel: discord.TextChannel | None = None):
        """Atur slowmode channel."""
        target = channel or ctx.channel
        await target.edit(slowmode_delay=seconds)
        await ctx.send(embed=await self._confirm(f"Slowmode {target.mention} diset ke **{seconds} detik**."))

    @app_commands.command(name="slowmode", description="Atur slowmode channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode_slash(self, interaction: discord.Interaction, seconds: int, channel: discord.TextChannel | None = None):
        target = channel or interaction.channel
        await target.edit(slowmode_delay=seconds)
        await interaction.response.send_message(embed=await self._confirm(f"Slowmode {target.mention} diset ke **{seconds} detik**."))

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def lock_prefix(self, ctx: commands.Context, channel: discord.TextChannel | None = None, *, reason: str = "Tidak ada alasan"):
        """Kunci channel supaya member tidak bisa kirim pesan."""
        target = channel or ctx.channel
        await target.set_permissions(ctx.guild.default_role, send_messages=False, reason=reason)
        await ctx.send(embed=await self._confirm(f"{target.mention} telah dikunci."))

    @app_commands.command(name="lock", description="Kunci channel (member tidak bisa kirim pesan).")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock_slash(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None, reason: str = "Tidak ada alasan"):
        target = channel or interaction.channel
        await target.set_permissions(interaction.guild.default_role, send_messages=False, reason=reason)
        await interaction.response.send_message(embed=await self._confirm(f"{target.mention} telah dikunci."))

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def unlock_prefix(self, ctx: commands.Context, channel: discord.TextChannel | None = None):
        """Buka kunci channel."""
        target = channel or ctx.channel
        await target.set_permissions(ctx.guild.default_role, send_messages=None, reason="Unlock")
        await ctx.send(embed=await self._confirm(f"{target.mention} telah dibuka kembali."))

    @app_commands.command(name="unlock", description="Buka kunci channel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock_slash(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None):
        target = channel or interaction.channel
        await target.set_permissions(interaction.guild.default_role, send_messages=None, reason="Unlock")
        await interaction.response.send_message(embed=await self._confirm(f"{target.mention} telah dibuka kembali."))

    @commands.command(name="purge", aliases=["clear"])
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def purge_prefix(self, ctx: commands.Context, amount: int, member: discord.Member | None = None):
        """Hapus banyak pesan sekaligus."""
        await ctx.message.delete()
        def check(m: discord.Message) -> bool:
            return member is None or m.author.id == member.id
        deleted = await ctx.channel.purge(limit=amount, check=check)
        msg = await ctx.send(embed=await self._confirm(f"{len(deleted)} pesan berhasil dihapus."))
        await msg.delete(delay=5)

    @app_commands.command(name="purge", description="Hapus banyak pesan sekaligus.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge_slash(self, interaction: discord.Interaction, amount: int, member: discord.Member | None = None):
        await interaction.response.defer(ephemeral=True)
        def check(m: discord.Message) -> bool:
            return member is None or m.author.id == member.id
        deleted = await interaction.channel.purge(limit=amount, check=check)
        await interaction.followup.send(embed=await self._confirm(f"{len(deleted)} pesan berhasil dihapus."), ephemeral=True)

    # ================= NICKNAME =================

    @commands.command(name="nickname", aliases=["nick"])
    @commands.has_permissions(manage_nicknames=True)
    @commands.guild_only()
    async def nickname_prefix(self, ctx: commands.Context, member: discord.Member, *, new_nick: str = ""):
        """Ubah nickname member."""
        await member.edit(nick=new_nick or None, reason=f"Diubah oleh {ctx.author}")
        await ctx.send(embed=await self._confirm(f"Nickname {member.mention} diubah ke **{new_nick or member.name}**."))

    @app_commands.command(name="nickname", description="Ubah nickname member (kosongkan untuk reset).")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nickname_slash(self, interaction: discord.Interaction, member: discord.Member, new_nick: str = ""):
        await member.edit(nick=new_nick or None, reason=f"Diubah oleh {interaction.user}")
        await interaction.response.send_message(embed=await self._confirm(f"Nickname {member.mention} diubah ke **{new_nick or member.name}**."))

    # ================= ROLE MANAGEMENT =================

    @commands.group(name="role", invoke_without_command=True)
    @commands.guild_only()
    async def role_group(self, ctx: commands.Context):
        """Kelola role member (tambah/hapus)."""
        await ctx.send(embed=JoyEmbed.info("Gunakan `!role add @member @role` atau `!role remove @member @role`."))

    @role_group.command(name="add")
    @commands.has_permissions(manage_roles=True)
    async def role_add(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        """Tambahkan role ke member."""
        await member.add_roles(role, reason=f"Ditambahkan oleh {ctx.author}")
        await ctx.send(embed=await self._confirm(f"Role {role.mention} ditambahkan ke {member.mention}."))

    @role_group.command(name="remove")
    @commands.has_permissions(manage_roles=True)
    async def role_remove(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        """Hapus role dari member."""
        await member.remove_roles(role, reason=f"Dihapus oleh {ctx.author}")
        await ctx.send(embed=await self._confirm(f"Role {role.mention} dihapus dari {member.mention}."))

    @app_commands.command(name="roleadd", description="Tambah role ke member.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def role_add_slash(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        await member.add_roles(role, reason=f"Ditambahkan oleh {interaction.user}")
        await interaction.response.send_message(embed=await self._confirm(f"Role {role.mention} ditambahkan ke {member.mention}."))

    @app_commands.command(name="roleremove", description="Hapus role dari member.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def role_remove_slash(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        await member.remove_roles(role, reason=f"Dihapus oleh {interaction.user}")
        await interaction.response.send_message(embed=await self._confirm(f"Role {role.mention} dihapus dari {member.mention}."))

    # ================= VOICE MODERATION =================

    @commands.command(name="voicemute")
    @commands.has_permissions(mute_members=True)
    @commands.guild_only()
    async def voicemute_prefix(self, ctx: commands.Context, member: discord.Member):
        """Voice mute member (server mute)."""
        await member.edit(mute=True, reason=f"Voice mute oleh {ctx.author}")
        await ctx.send(embed=await self._confirm(f"{member.mention} di-voice mute."))

    @commands.command(name="voiceunmute")
    @commands.has_permissions(mute_members=True)
    @commands.guild_only()
    async def voiceunmute_prefix(self, ctx: commands.Context, member: discord.Member):
        """Voice unmute member."""
        await member.edit(mute=False, reason=f"Voice unmute oleh {ctx.author}")
        await ctx.send(embed=await self._confirm(f"{member.mention} di-voice unmute."))

    @commands.command(name="voicekick")
    @commands.has_permissions(move_members=True)
    @commands.guild_only()
    async def voicekick_prefix(self, ctx: commands.Context, member: discord.Member):
        """Keluarkan member dari voice channel."""
        await member.move_to(None, reason=f"Voice kick oleh {ctx.author}")
        await ctx.send(embed=await self._confirm(f"{member.mention} dikeluarkan dari voice channel."))

    @commands.command(name="voicemove")
    @commands.has_permissions(move_members=True)
    @commands.guild_only()
    async def voicemove_prefix(self, ctx: commands.Context, member: discord.Member, channel: discord.VoiceChannel):
        """Pindahkan member ke voice channel lain."""
        await member.move_to(channel, reason=f"Voice move oleh {ctx.author}")
        await ctx.send(embed=await self._confirm(f"{member.mention} dipindahkan ke {channel.mention}."))

    @app_commands.command(name="voicemute", description="Voice mute member (server mute).")
    @app_commands.checks.has_permissions(mute_members=True)
    async def voicemute_slash(self, interaction: discord.Interaction, member: discord.Member):
        await member.edit(mute=True, reason=f"Voice mute oleh {interaction.user}")
        await interaction.response.send_message(embed=await self._confirm(f"{member.mention} di-voice mute."))

    @app_commands.command(name="voiceunmute", description="Voice unmute member.")
    @app_commands.checks.has_permissions(mute_members=True)
    async def voiceunmute_slash(self, interaction: discord.Interaction, member: discord.Member):
        await member.edit(mute=False, reason=f"Voice unmute oleh {interaction.user}")
        await interaction.response.send_message(embed=await self._confirm(f"{member.mention} di-voice unmute."))

    @app_commands.command(name="voicekick", description="Keluarkan member dari voice channel.")
    @app_commands.checks.has_permissions(move_members=True)
    async def voicekick_slash(self, interaction: discord.Interaction, member: discord.Member):
        await member.move_to(None, reason=f"Voice kick oleh {interaction.user}")
        await interaction.response.send_message(embed=await self._confirm(f"{member.mention} dikeluarkan dari voice channel."))

    @app_commands.command(name="voicemove", description="Pindahkan member ke voice channel lain.")
    @app_commands.checks.has_permissions(move_members=True)
    async def voicemove_slash(self, interaction: discord.Interaction, member: discord.Member, channel: discord.VoiceChannel):
        await member.move_to(channel, reason=f"Voice move oleh {interaction.user}")
        await interaction.response.send_message(embed=await self._confirm(f"{member.mention} dipindahkan ke {channel.mention}."))

    # ================= SETUP: mod log channel & mute role & log toggles =================

    @commands.command(name="setmodlog")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setmodlog_prefix(self, ctx: commands.Context, channel: discord.TextChannel | None = None):
        """Atur channel untuk moderation log."""
        await self.guild_config_service.set_mod_log_channel(ctx.guild.id, channel.id if channel else None)
        await ctx.send(embed=await self._confirm(f"Moderation log channel: {channel.mention if channel else 'dinonaktifkan'}."))

    @app_commands.command(name="setmodlog", description="Set channel untuk moderation log.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setmodlog_slash(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None):
        await self.guild_config_service.set_mod_log_channel(interaction.guild_id, channel.id if channel else None)
        await interaction.response.send_message(embed=await self._confirm(f"Moderation log channel: {channel.mention if channel else 'dinonaktifkan'}."))

    @commands.command(name="setmuterole")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setmuterole_prefix(self, ctx: commands.Context, role: discord.Role):
        """Atur role yang dipakai untuk command mute."""
        await self.guild_config_service.set_mute_role_id(ctx.guild.id, role.id)
        await ctx.send(embed=await self._confirm(f"Mute role diset ke {role.mention}."))

    @app_commands.command(name="setmuterole", description="Set role yang dipakai untuk command mute.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setmuterole_slash(self, interaction: discord.Interaction, role: discord.Role):
        await self.guild_config_service.set_mute_role_id(interaction.guild_id, role.id)
        await interaction.response.send_message(embed=await self._confirm(f"Mute role diset ke {role.mention}."))

    @commands.command(name="logconfig")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def logconfig_prefix(self, ctx: commands.Context, category: str, state: str):
        """Aktifkan/nonaktifkan kategori moderation log tertentu."""
        column = f"log_{category.lower()}"
        try:
            await self.mod_service.set_log_config_field(ctx.guild.id, column, state.lower() == "on")
        except ValueError:
            await ctx.send(embed=JoyEmbed.error(
                "Kategori tidak valid. Pilihan: join_leave, message_delete, message_edit, role_update, "
                "nickname, moderation_action, voice, emoji_sticker, thread, webhook"
            ))
            return
        await ctx.send(embed=await self._confirm(f"Log `{category}`: **{state.upper()}**."))

    # ================= MODERATION LOG: PASSIVE LISTENERS =================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self._send_log(member.guild, "log_join_leave", JoyEmbed.success(
            f"{member.mention} (`{member.id}`) bergabung ke server.\nAkun dibuat: {discord.utils.format_dt(member.created_at, 'R')}",
            title=f"{emoji.member_join} Member Join",
        ))

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self._send_log(member.guild, "log_join_leave", JoyEmbed.warning(
            f"{member.mention} (`{member.id}`) meninggalkan server.",
            title=f"{emoji.member_leave} Member Leave",
        ))

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or message.guild is None or not message.content:
            return
        await self._send_log(message.guild, "log_message_delete", JoyEmbed.warning(
            f"**Author:** {message.author.mention}\n**Channel:** {message.channel.mention}\n**Isi:** {message.content[:500]}",
            title=f"{emoji.warning} Pesan Dihapus",
        ))

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.guild is None or before.content == after.content:
            return
        await self._send_log(before.guild, "log_message_edit", JoyEmbed.info(
            f"**Author:** {before.author.mention}\n**Channel:** {before.channel.mention}\n"
            f"**Sebelum:** {before.content[:400]}\n**Sesudah:** {after.content[:400]}",
            title=f"{emoji.info} Pesan Diedit",
        ))

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            await self._send_log(before.guild, "log_nickname", JoyEmbed.info(
                f"**User:** {after.mention}\n**Sebelum:** {before.nick or before.name}\n**Sesudah:** {after.nick or after.name}",
                title=f"{emoji.info} Nickname Diubah",
            ))
        if set(before.roles) != set(after.roles):
            added = set(after.roles) - set(before.roles)
            removed = set(before.roles) - set(after.roles)
            desc_parts = [f"**User:** {after.mention}"]
            if added:
                desc_parts.append("**Ditambah:** " + ", ".join(r.mention for r in added))
            if removed:
                desc_parts.append("**Dihapus:** " + ", ".join(r.mention for r in removed))
            await self._send_log(before.guild, "log_role_update", JoyEmbed.info(
                "\n".join(desc_parts), title=f"{emoji.info} Role Diperbarui",
            ))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel == after.channel:
            return
        if before.channel is None and after.channel is not None:
            desc = f"{member.mention} bergabung ke voice **{after.channel.name}**."
        elif before.channel is not None and after.channel is None:
            desc = f"{member.mention} keluar dari voice **{before.channel.name}**."
        else:
            desc = f"{member.mention} pindah dari **{before.channel.name}** ke **{after.channel.name}**."
        await self._send_log(member.guild, "log_voice", JoyEmbed.info(desc, title=f"{emoji.info} Voice Activity"))

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before, after):
        await self._send_log(guild, "log_emoji_sticker", JoyEmbed.info(
            f"Jumlah emoji berubah: {len(before)} → {len(after)}.", title=f"{emoji.info} Emoji Diperbarui",
        ))

    @commands.Cog.listener()
    async def on_guild_stickers_update(self, guild: discord.Guild, before, after):
        await self._send_log(guild, "log_emoji_sticker", JoyEmbed.info(
            f"Jumlah sticker berubah: {len(before)} → {len(after)}.", title=f"{emoji.info} Sticker Diperbarui",
        ))

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        await self._send_log(thread.guild, "log_thread", JoyEmbed.success(
            f"Thread **{thread.name}** dibuat di {thread.parent.mention if thread.parent else '-'}.",
            title=f"{emoji.info} Thread Dibuat",
        ))

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        await self._send_log(thread.guild, "log_thread", JoyEmbed.warning(
            f"Thread **{thread.name}** dihapus.", title=f"{emoji.info} Thread Dihapus",
        ))

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel):
        await self._send_log(channel.guild, "log_webhook", JoyEmbed.info(
            f"Konfigurasi webhook di {channel.mention} diperbarui.", title=f"{emoji.info} Webhook Diperbarui",
        ))


async def setup(bot: JoyUniverse):
    await bot.add_cog(Moderation(bot))
