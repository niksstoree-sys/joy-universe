"""
Cog Leveling System untuk JOY UNIVERSE (Stage 4) — fitur utama bot.

Text XP (dengan anti-spam cooldown & daily limit), Voice XP (background
task tiap menit), Rank Card & Leaderboard Card berupa IMAGE (Pillow, bukan
embed teks biasa), Prestige, dan Role Reward per level/prestige.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.core.bot import JoyUniverse
from bot.services.leveling_service import LevelingService
from bot.utils.embeds import JoyEmbed
from bot.utils.emojis import emoji
from bot.utils.rank_card_generator import generate_leaderboard_card, generate_rank_card
from bot.utils.xp_curve import level_from_xp

logger = logging.getLogger("joyuniverse.cogs.leveling")

LEADERBOARD_PAGE_SIZE = 10


def _manage_guild_prefix():
    return commands.has_permissions(manage_guild=True)


def _manage_guild_slash():
    return app_commands.checks.has_permissions(manage_guild=True)


def _resolve_levelup_text(template: str, member: discord.Member, guild: discord.Guild, level: int, prestige: int) -> str:
    replacements = {
        "{user_mention}": member.mention,
        "{user}": member.mention,
        "{user_name}": member.display_name,
        "{server}": guild.name,
        "{level}": str(level),
        "{prestige}": str(prestige),
    }
    text = template
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


class Leveling(commands.Cog):
    """Prefix: `!rank`, `!leaderboard`, `!level ...` (config). Slash: `/rank`, `/leaderboard`, `/level ...`."""

    level_group = app_commands.Group(name="level", description="Konfigurasi & fitur leveling server.")

    def __init__(self, bot: JoyUniverse):
        self.bot = bot
        self.service = LevelingService(bot.db)
        self.voice_xp_loop.start()

    def cog_unload(self) -> None:
        self.voice_xp_loop.cancel()

    # ================= VOICE XP BACKGROUND TASK =================

    @tasks.loop(minutes=1)
    async def voice_xp_loop(self):
        try:
            for guild in self.bot.guilds:
                config = await self.service.get_config(guild.id)
                if not config.voice_xp_enabled:
                    continue
                for vc in guild.voice_channels:
                    if guild.afk_channel is not None and vc.id == guild.afk_channel.id:
                        continue
                    human_members = [m for m in vc.members if not m.bot]
                    if len(human_members) < config.voice_xp_min_members:
                        continue
                    for member in human_members:
                        if member.voice and (member.voice.self_deaf or member.voice.deaf):
                            continue
                        await self._award_voice_xp(guild, member, config)
        except Exception:
            logger.exception("Error di voice XP loop")

    @voice_xp_loop.before_loop
    async def before_voice_xp_loop(self):
        await self.bot.wait_until_ready()

    async def _award_voice_xp(self, guild: discord.Guild, member: discord.Member, config) -> None:
        result = await self.service.add_voice_xp(guild.id, member.id, minutes=1)
        if result.leveled_up:
            await self._handle_level_up(guild, member, result.new_level, fallback_channel=None)

    # ================= TEXT XP LISTENER =================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        config = await self.service.get_config(message.guild.id)
        if not config.enabled:
            return

        try:
            result = await self.service.add_text_xp(message.guild.id, message.author.id)
        except Exception:
            logger.exception("Gagal memberi text XP di guild %s", message.guild.id)
            return

        if result.leveled_up and isinstance(message.author, discord.Member):
            await self._handle_level_up(message.guild, message.author, result.new_level, fallback_channel=message.channel)

    # ================= LEVEL UP HANDLER (embed/card + role reward) =================

    async def _handle_level_up(
        self,
        guild: discord.Guild,
        member: discord.Member,
        new_level: int,
        fallback_channel: discord.abc.Messageable | None,
    ) -> None:
        config = await self.service.get_config(guild.id)

        # Role reward per level
        try:
            role_ids = await self.service.get_role_rewards_up_to(guild.id, new_level)
            roles_to_add = [
                guild.get_role(int(rid)) for rid in role_ids if guild.get_role(int(rid)) is not None
            ]
            missing_roles = [r for r in roles_to_add if r not in member.roles]
            if missing_roles:
                await member.add_roles(*missing_roles, reason=f"Level reward (Level {new_level})")
        except discord.Forbidden:
            logger.warning("Bot tidak punya izin memberi role reward di guild %s", guild.id)
        except Exception:
            logger.exception("Gagal memberi role reward level di guild %s", guild.id)

        if not config.level_up_message_enabled:
            return

        channel: discord.abc.Messageable | None = None
        if config.level_up_channel_id:
            channel = guild.get_channel(int(config.level_up_channel_id))
        if channel is None:
            channel = fallback_channel
        if channel is None:
            return

        user_data = await self.service.get_user(guild.id, member.id)
        text = _resolve_levelup_text(
            config.level_up_message or "{user_mention} naik ke **Level {level}**!",
            member, guild, new_level, user_data.prestige,
        )

        try:
            if config.level_up_use_card:
                rank = await self.service.get_rank(guild.id, member.id)
                _, xp_into, xp_needed = level_from_xp(user_data.xp)
                file = await generate_rank_card(
                    member,
                    level=new_level,
                    prestige=user_data.prestige,
                    rank=rank,
                    xp_into=xp_into,
                    xp_needed=xp_needed,
                    total_messages=user_data.total_messages,
                    voice_minutes=user_data.voice_minutes,
                    background_url=config.rank_card_background,
                )
                await channel.send(content=text, file=file)
            else:
                await channel.send(embed=JoyEmbed.success(text, title=f"{emoji.level_up} Level Up!"))
        except discord.HTTPException:
            logger.exception("Gagal mengirim pesan level up di guild %s", guild.id)

    # ================= PREFIX: rank & leaderboard =================

    @commands.command(name="rank", aliases=["lvl"])
    @commands.guild_only()
    async def rank_prefix(self, ctx: commands.Context, member: discord.Member | None = None):
        """Menampilkan rank card kamu atau member lain."""
        target = member or ctx.author
        await self._send_rank(ctx, target)

    @commands.command(name="leaderboard", aliases=["lb", "top"])
    @commands.guild_only()
    async def leaderboard_prefix(self, ctx: commands.Context, page: int = 1):
        """Menampilkan leaderboard XP server (dalam bentuk gambar)."""
        await self._send_leaderboard(ctx, page)

    @commands.command(name="prestige")
    @commands.guild_only()
    async def prestige_prefix(self, ctx: commands.Context):
        """Prestige kalau level kamu sudah cukup tinggi."""
        await self._do_prestige(ctx, ctx.author)

    # ================= PREFIX: !level (config, admin) =================

    @commands.group(name="level", invoke_without_command=True)
    @commands.guild_only()
    async def level_config_group(self, ctx: commands.Context):
        """Menampilkan konfigurasi leveling saat ini."""
        config = await self.service.get_config(ctx.guild.id)
        embed = JoyEmbed.info(
            f"**Status:** {'Aktif' if config.enabled else 'Nonaktif'}\n"
            f"**XP per pesan:** {config.xp_per_message_min}-{config.xp_per_message_max}\n"
            f"**Cooldown:** {config.xp_cooldown_seconds} detik\n"
            f"**Daily limit:** {config.daily_xp_limit or 'Tidak dibatasi'}\n"
            f"**Voice XP:** {'Aktif' if config.voice_xp_enabled else 'Nonaktif'} ({config.voice_xp_per_minute} XP/menit)\n"
            f"**Prestige:** {'Aktif' if config.prestige_enabled else 'Nonaktif'} (butuh Level {config.prestige_required_level})\n"
            f"**Level Up Card:** {'Aktif' if config.level_up_use_card else 'Embed teks saja'}",
            title=f"{emoji.settings} Konfigurasi Leveling",
        )
        await ctx.send(embed=embed)

    @level_config_group.command(name="toggle")
    @_manage_guild_prefix()
    async def level_toggle(self, ctx: commands.Context, state: str):
        """Aktifkan atau nonaktifkan leveling system."""
        await self.service.set_config_field(ctx.guild.id, "enabled", int(state.lower() == "on"))
        await ctx.send(embed=JoyEmbed.success(f"Leveling system: **{state.upper()}**."))

    @level_config_group.command(name="setxp")
    @_manage_guild_prefix()
    async def level_setxp(self, ctx: commands.Context, min_xp: int, max_xp: int):
        """Atur rentang XP per pesan."""
        if min_xp > max_xp or min_xp < 1:
            await ctx.send(embed=JoyEmbed.error("min_xp harus >= 1 dan <= max_xp."))
            return
        await self.service.set_config_field(ctx.guild.id, "xp_per_message_min", min_xp)
        await self.service.set_config_field(ctx.guild.id, "xp_per_message_max", max_xp)
        await ctx.send(embed=JoyEmbed.success(f"XP per pesan diset ke **{min_xp}-{max_xp}**."))

    @level_config_group.command(name="cooldown")
    @_manage_guild_prefix()
    async def level_cooldown(self, ctx: commands.Context, seconds: int):
        """Atur cooldown anti-spam XP (detik)."""
        await self.service.set_config_field(ctx.guild.id, "xp_cooldown_seconds", seconds)
        await ctx.send(embed=JoyEmbed.success(f"Cooldown XP diset ke **{seconds} detik**."))

    @level_config_group.command(name="dailylimit")
    @_manage_guild_prefix()
    async def level_dailylimit(self, ctx: commands.Context, limit: int):
        """Atur batas XP harian (0 = tidak dibatasi)."""
        await self.service.set_config_field(ctx.guild.id, "daily_xp_limit", max(0, limit))
        await ctx.send(embed=JoyEmbed.success(f"Daily XP limit diset ke **{limit if limit > 0 else 'Tidak dibatasi'}**."))

    @level_config_group.command(name="voicexp")
    @_manage_guild_prefix()
    async def level_voicexp(self, ctx: commands.Context, state: str, xp_per_minute: int | None = None):
        """Aktifkan/nonaktifkan dan atur Voice XP."""
        await self.service.set_config_field(ctx.guild.id, "voice_xp_enabled", int(state.lower() == "on"))
        if xp_per_minute is not None:
            await self.service.set_config_field(ctx.guild.id, "voice_xp_per_minute", xp_per_minute)
        await ctx.send(embed=JoyEmbed.success(f"Voice XP: **{state.upper()}**."))

    @level_config_group.command(name="levelupmessage")
    @_manage_guild_prefix()
    async def level_levelupmessage(self, ctx: commands.Context, *, text: str):
        """Atur teks pesan saat member naik level."""
        await self.service.set_config_field(ctx.guild.id, "level_up_message", text)
        await ctx.send(embed=JoyEmbed.success("Pesan level up diperbarui."))

    @level_config_group.command(name="levelupchannel")
    @_manage_guild_prefix()
    async def level_levelupchannel(self, ctx: commands.Context, channel: discord.TextChannel | None = None):
        """Atur channel khusus untuk pesan level up."""
        await self.service.set_config_field(ctx.guild.id, "level_up_channel_id", str(channel.id) if channel else None)
        await ctx.send(embed=JoyEmbed.success(f"Channel level up: {channel.mention if channel else 'sama seperti channel chat'}."))

    @level_config_group.command(name="levelupcard")
    @_manage_guild_prefix()
    async def level_levelupcard(self, ctx: commands.Context, state: str):
        """Atur apakah level up pakai rank card (gambar) atau embed teks saja."""
        await self.service.set_config_field(ctx.guild.id, "level_up_use_card", int(state.lower() == "on"))
        await ctx.send(embed=JoyEmbed.success(f"Level up pakai rank card: **{state.upper()}**."))

    @level_config_group.command(name="prestigerequired")
    @_manage_guild_prefix()
    async def level_prestigerequired(self, ctx: commands.Context, level: int):
        """Atur level minimal untuk bisa prestige."""
        await self.service.set_config_field(ctx.guild.id, "prestige_required_level", level)
        await ctx.send(embed=JoyEmbed.success(f"Level minimal prestige diset ke **{level}**."))

    @level_config_group.command(name="rankbackground")
    @_manage_guild_prefix()
    async def level_rankbackground(self, ctx: commands.Context, url: str):
        """Atur background custom untuk rank card."""
        value = None if url.lower() == "none" else url
        await self.service.set_config_field(ctx.guild.id, "rank_card_background", value)
        await ctx.send(embed=JoyEmbed.success("Background rank card diperbarui."))

    @level_config_group.command(name="leaderboardbackground")
    @_manage_guild_prefix()
    async def level_leaderboardbackground(self, ctx: commands.Context, url: str):
        """Atur background custom untuk leaderboard card."""
        value = None if url.lower() == "none" else url
        await self.service.set_config_field(ctx.guild.id, "leaderboard_background", value)
        await ctx.send(embed=JoyEmbed.success("Background leaderboard card diperbarui."))

    @level_config_group.command(name="rolereward")
    @_manage_guild_prefix()
    async def level_rolereward(self, ctx: commands.Context, level: int, role: discord.Role):
        """Atur role reward untuk level tertentu."""
        await self.service.set_level_role_reward(ctx.guild.id, level, role.id)
        await ctx.send(embed=JoyEmbed.success(f"Role {role.mention} akan diberikan saat mencapai **Level {level}**."))

    @level_config_group.command(name="removerolereward")
    @_manage_guild_prefix()
    async def level_removerolereward(self, ctx: commands.Context, level: int):
        """Hapus role reward dari level tertentu."""
        await self.service.remove_level_role_reward(ctx.guild.id, level)
        await ctx.send(embed=JoyEmbed.success(f"Role reward untuk Level {level} dihapus."))

    @level_config_group.command(name="prestigerolereward")
    @_manage_guild_prefix()
    async def level_prestigerolereward(self, ctx: commands.Context, prestige: int, role: discord.Role):
        """Atur role reward untuk prestige tertentu."""
        await self.service.set_prestige_role_reward(ctx.guild.id, prestige, role.id)
        await ctx.send(embed=JoyEmbed.success(f"Role {role.mention} akan diberikan saat mencapai **Prestige {prestige}**."))

    @level_config_group.command(name="resetuser")
    @_manage_guild_prefix()
    async def level_resetuser(self, ctx: commands.Context, member: discord.Member):
        """Reset data level seorang member."""
        await self.service.reset_user(ctx.guild.id, member.id)
        await ctx.send(embed=JoyEmbed.success(f"Data level {member.mention} sudah direset."))

    # ================= SLASH: /rank & /leaderboard (top-level) =================

    @app_commands.command(name="rank", description="Menampilkan rank card kamu atau member lain.")
    async def rank_slash(self, interaction: discord.Interaction, member: discord.Member | None = None):
        target = member or interaction.user
        await interaction.response.defer()
        await self._send_rank(interaction, target)

    @app_commands.command(name="leaderboard", description="Menampilkan leaderboard XP server.")
    async def leaderboard_slash(self, interaction: discord.Interaction, page: int = 1):
        await interaction.response.defer()
        await self._send_leaderboard(interaction, page)

    @app_commands.command(name="prestige", description="Prestige kalau level kamu sudah cukup.")
    async def prestige_slash(self, interaction: discord.Interaction):
        await self._do_prestige(interaction, interaction.user)

    # ================= SLASH: /level ... (config, GROUP) =================

    @level_group.command(name="settings", description="Menampilkan konfigurasi leveling saat ini.")
    async def level_settings_slash(self, interaction: discord.Interaction):
        config = await self.service.get_config(interaction.guild_id)
        embed = JoyEmbed.info(
            f"**Status:** {'Aktif' if config.enabled else 'Nonaktif'}\n"
            f"**XP per pesan:** {config.xp_per_message_min}-{config.xp_per_message_max}\n"
            f"**Cooldown:** {config.xp_cooldown_seconds} detik\n"
            f"**Daily limit:** {config.daily_xp_limit or 'Tidak dibatasi'}\n"
            f"**Voice XP:** {'Aktif' if config.voice_xp_enabled else 'Nonaktif'} ({config.voice_xp_per_minute} XP/menit)\n"
            f"**Prestige:** {'Aktif' if config.prestige_enabled else 'Nonaktif'} (butuh Level {config.prestige_required_level})",
            title=f"{emoji.settings} Konfigurasi Leveling",
        )
        await interaction.response.send_message(embed=embed)

    @level_group.command(name="toggle", description="Aktifkan/nonaktifkan leveling system.")
    @_manage_guild_slash()
    async def level_toggle_slash(self, interaction: discord.Interaction, state: str):
        await self.service.set_config_field(interaction.guild_id, "enabled", int(state.lower() == "on"))
        await interaction.response.send_message(embed=JoyEmbed.success(f"Leveling system: **{state.upper()}**."))

    @level_group.command(name="setxp", description="Atur rentang XP per pesan.")
    @_manage_guild_slash()
    async def level_setxp_slash(self, interaction: discord.Interaction, min_xp: int, max_xp: int):
        if min_xp > max_xp or min_xp < 1:
            await interaction.response.send_message(embed=JoyEmbed.error("min_xp harus >= 1 dan <= max_xp."), ephemeral=True)
            return
        await self.service.set_config_field(interaction.guild_id, "xp_per_message_min", min_xp)
        await self.service.set_config_field(interaction.guild_id, "xp_per_message_max", max_xp)
        await interaction.response.send_message(embed=JoyEmbed.success(f"XP per pesan diset ke **{min_xp}-{max_xp}**."))

    @level_group.command(name="cooldown", description="Atur cooldown anti-spam XP (detik).")
    @_manage_guild_slash()
    async def level_cooldown_slash(self, interaction: discord.Interaction, seconds: int):
        await self.service.set_config_field(interaction.guild_id, "xp_cooldown_seconds", seconds)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Cooldown XP diset ke **{seconds} detik**."))

    @level_group.command(name="dailylimit", description="Atur batas XP harian (0 = tidak dibatasi).")
    @_manage_guild_slash()
    async def level_dailylimit_slash(self, interaction: discord.Interaction, limit: int):
        await self.service.set_config_field(interaction.guild_id, "daily_xp_limit", max(0, limit))
        await interaction.response.send_message(embed=JoyEmbed.success(f"Daily XP limit diset ke **{limit if limit > 0 else 'Tidak dibatasi'}**."))

    @level_group.command(name="voicexp", description="Toggle & atur Voice XP.")
    @_manage_guild_slash()
    async def level_voicexp_slash(self, interaction: discord.Interaction, state: str, xp_per_minute: int | None = None):
        await self.service.set_config_field(interaction.guild_id, "voice_xp_enabled", int(state.lower() == "on"))
        if xp_per_minute is not None:
            await self.service.set_config_field(interaction.guild_id, "voice_xp_per_minute", xp_per_minute)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Voice XP: **{state.upper()}**."))

    @level_group.command(name="levelupmessage", description="Atur teks pesan level up.")
    @_manage_guild_slash()
    async def level_levelupmessage_slash(self, interaction: discord.Interaction, text: str):
        await self.service.set_config_field(interaction.guild_id, "level_up_message", text)
        await interaction.response.send_message(embed=JoyEmbed.success("Pesan level up diperbarui."))

    @level_group.command(name="levelupchannel", description="Atur channel khusus untuk pesan level up.")
    @_manage_guild_slash()
    async def level_levelupchannel_slash(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None):
        await self.service.set_config_field(interaction.guild_id, "level_up_channel_id", str(channel.id) if channel else None)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Channel level up: {channel.mention if channel else 'sama seperti channel chat'}."))

    @level_group.command(name="levelupcard", description="Toggle rank card di pesan level up.")
    @_manage_guild_slash()
    async def level_levelupcard_slash(self, interaction: discord.Interaction, state: str):
        await self.service.set_config_field(interaction.guild_id, "level_up_use_card", int(state.lower() == "on"))
        await interaction.response.send_message(embed=JoyEmbed.success(f"Level up pakai rank card: **{state.upper()}**."))

    @level_group.command(name="prestigerequired", description="Atur level minimal untuk prestige.")
    @_manage_guild_slash()
    async def level_prestigerequired_slash(self, interaction: discord.Interaction, level: int):
        await self.service.set_config_field(interaction.guild_id, "prestige_required_level", level)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Level minimal prestige diset ke **{level}**."))

    @level_group.command(name="rankbackground", description="Set background custom untuk rank card.")
    @_manage_guild_slash()
    async def level_rankbackground_slash(self, interaction: discord.Interaction, url: str):
        value = None if url.lower() == "none" else url
        await self.service.set_config_field(interaction.guild_id, "rank_card_background", value)
        await interaction.response.send_message(embed=JoyEmbed.success("Background rank card diperbarui."))

    @level_group.command(name="leaderboardbackground", description="Set background custom untuk leaderboard card.")
    @_manage_guild_slash()
    async def level_leaderboardbackground_slash(self, interaction: discord.Interaction, url: str):
        value = None if url.lower() == "none" else url
        await self.service.set_config_field(interaction.guild_id, "leaderboard_background", value)
        await interaction.response.send_message(embed=JoyEmbed.success("Background leaderboard card diperbarui."))

    @level_group.command(name="rolereward", description="Set role reward untuk level tertentu.")
    @_manage_guild_slash()
    async def level_rolereward_slash(self, interaction: discord.Interaction, level: int, role: discord.Role):
        await self.service.set_level_role_reward(interaction.guild_id, level, role.id)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Role {role.mention} akan diberikan saat mencapai **Level {level}**."))

    @level_group.command(name="removerolereward", description="Hapus role reward untuk level tertentu.")
    @_manage_guild_slash()
    async def level_removerolereward_slash(self, interaction: discord.Interaction, level: int):
        await self.service.remove_level_role_reward(interaction.guild_id, level)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Role reward untuk Level {level} dihapus."))

    @level_group.command(name="prestigerolereward", description="Set role reward untuk prestige tertentu.")
    @_manage_guild_slash()
    async def level_prestigerolereward_slash(self, interaction: discord.Interaction, prestige: int, role: discord.Role):
        await self.service.set_prestige_role_reward(interaction.guild_id, prestige, role.id)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Role {role.mention} akan diberikan saat mencapai **Prestige {prestige}**."))

    @level_group.command(name="resetuser", description="Reset data level seorang member.")
    @_manage_guild_slash()
    async def level_resetuser_slash(self, interaction: discord.Interaction, member: discord.Member):
        await self.service.reset_user(interaction.guild_id, member.id)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Data level {member.mention} sudah direset."))

    # ================= SHARED LOGIC =================

    async def _send_rank(self, ctx_or_interaction, target: discord.Member) -> None:
        guild = target.guild
        config = await self.service.get_config(guild.id)
        user_data = await self.service.get_user(guild.id, target.id)
        level, xp_into, xp_needed = level_from_xp(user_data.xp)
        rank = await self.service.get_rank(guild.id, target.id)

        file = await generate_rank_card(
            target,
            level=level,
            prestige=user_data.prestige,
            rank=rank,
            xp_into=xp_into,
            xp_needed=xp_needed,
            total_messages=user_data.total_messages,
            voice_minutes=user_data.voice_minutes,
            background_url=config.rank_card_background,
        )

        if isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.followup.send(file=file)
        else:
            await ctx_or_interaction.send(file=file)

    async def _send_leaderboard(self, ctx_or_interaction, page: int) -> None:
        guild = ctx_or_interaction.guild
        page = max(1, page)
        offset = (page - 1) * LEADERBOARD_PAGE_SIZE

        config = await self.service.get_config(guild.id)
        top_users = await self.service.get_leaderboard(guild.id, limit=LEADERBOARD_PAGE_SIZE, offset=offset)

        if not top_users:
            embed = JoyEmbed.info("Belum ada data XP di halaman ini.")
            if isinstance(ctx_or_interaction, discord.Interaction):
                await ctx_or_interaction.followup.send(embed=embed)
            else:
                await ctx_or_interaction.send(embed=embed)
            return

        entries = []
        for idx, user_data in enumerate(top_users):
            member = guild.get_member(int(user_data.user_id))
            level, _, _ = level_from_xp(user_data.xp)
            entries.append({
                "rank": offset + idx + 1,
                "member": member,
                "display_name": member.display_name if member else f"User {user_data.user_id}",
                "level": level,
                "prestige": user_data.prestige,
                "xp": user_data.xp,
            })

        file = await generate_leaderboard_card(guild, entries, background_url=config.leaderboard_background)

        if isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.followup.send(file=file)
        else:
            await ctx_or_interaction.send(file=file)

    async def _do_prestige(self, ctx_or_interaction, member: discord.Member) -> None:
        guild = member.guild
        config = await self.service.get_config(guild.id)

        if not config.prestige_enabled:
            embed = JoyEmbed.error("Fitur prestige tidak aktif di server ini.")
            await self._reply(ctx_or_interaction, embed)
            return

        can_do, current_level, required_level = await self.service.can_prestige(guild.id, member.id)
        if not can_do:
            embed = JoyEmbed.warning(f"Kamu butuh **Level {required_level}** untuk prestige. Level kamu sekarang: **{current_level}**.")
            await self._reply(ctx_or_interaction, embed)
            return

        new_prestige = await self.service.do_prestige(guild.id, member.id)

        role_id = await self.service.get_role_reward_for_prestige(guild.id, new_prestige)
        if role_id:
            role = guild.get_role(int(role_id))
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason=f"Prestige {new_prestige}")
                except discord.Forbidden:
                    logger.warning("Bot tidak punya izin memberi prestige role di guild %s", guild.id)

        embed = JoyEmbed.success(f"Selamat! Kamu sekarang **Prestige {new_prestige}**. XP dan level direset dari awal.", title=f"{emoji.premium} Prestige!")
        await self._reply(ctx_or_interaction, embed)

    async def _reply(self, ctx_or_interaction, embed: discord.Embed) -> None:
        if isinstance(ctx_or_interaction, discord.Interaction):
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(embed=embed)
            else:
                await ctx_or_interaction.response.send_message(embed=embed)
        else:
            await ctx_or_interaction.send(embed=embed)


async def setup(bot: JoyUniverse):
    await bot.add_cog(Leveling(bot))
