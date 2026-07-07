"""
Cog Auto Moderation untuk JOY UNIVERSE (Stage 6).

Semua rate-limiting (spam, anti-raid) dilacak in-memory per proses bot
(cukup untuk kebutuhan real-time; tidak perlu persist ke DB). Konfigurasi
tiap rule disimpan di database lewat AutomodService.
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict, defaultdict, deque
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.bot import JoyUniverse
from bot.services.automod_service import VALID_ACTIONS, AutomodService
from bot.utils.automod_detectors import (
    contains_badword,
    contains_invite,
    contains_link,
    count_mentions,
    is_excessive_caps,
    looks_like_scam,
)
from bot.utils.embeds import JoyEmbed
from bot.utils.emojis import emoji

logger = logging.getLogger("joyuniverse.cogs.automod")

GHOST_PING_WINDOW_SECONDS = 60
MENTION_TRACK_MAX_SIZE = 2000


def _manage_guild_prefix():
    return commands.has_permissions(manage_guild=True)


def _manage_guild_slash():
    return app_commands.checks.has_permissions(manage_guild=True)


class AutoMod(commands.GroupCog, name="automod"):
    """Prefix: `!automod ...`. Slash: `/automod ...`."""

    def __init__(self, bot: JoyUniverse):
        self.bot = bot
        self.service = AutomodService(bot.db)

        self._message_times: dict[tuple[int, int], deque] = defaultdict(deque)
        self._join_times: dict[int, deque] = defaultdict(deque)
        self._raid_lockdown_until: dict[int, float] = {}
        self._mention_messages: OrderedDict[int, tuple[list[int], float]] = OrderedDict()

    # ================= HELPERS =================

    def _track_mention_message(self, message_id: int, mentioned_ids: list[int]) -> None:
        self._mention_messages[message_id] = (mentioned_ids, time.time())
        while len(self._mention_messages) > MENTION_TRACK_MAX_SIZE:
            self._mention_messages.popitem(last=False)

    async def _is_whitelisted(self, message: discord.Message) -> bool:
        if message.author.guild_permissions.manage_guild:
            return True
        whitelist = await self.service.get_whitelist(message.guild.id)
        if str(message.author.id) in whitelist.get("user", set()):
            return True
        if str(message.channel.id) in whitelist.get("channel", set()):
            return True
        author_role_ids = {str(r.id) for r in message.author.roles}
        if author_role_ids & whitelist.get("role", set()):
            return True
        return False

    def _record_and_check_spam(self, guild_id: int, user_id: int, threshold: int, interval: int) -> bool:
        key = (guild_id, user_id)
        now = time.time()
        dq = self._message_times[key]
        dq.append(now)
        while dq and now - dq[0] > interval:
            dq.popleft()
        if len(dq) >= threshold:
            dq.clear()
            return True
        return False

    async def _apply_message_action(
        self, message: discord.Message, action: str, timeout_seconds: int, rule: str, detail: str = ""
    ) -> None:
        guild = message.guild
        member = message.author

        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

        try:
            if action == "timeout" and isinstance(member, discord.Member):
                await member.timeout(discord.utils.utcnow() + timedelta(seconds=timeout_seconds), reason=f"Automod: {rule}")
            elif action == "kick" and isinstance(member, discord.Member):
                await member.kick(reason=f"Automod: {rule}")
            elif action == "ban" and isinstance(member, discord.Member):
                await member.ban(reason=f"Automod: {rule}", delete_message_seconds=60)
        except discord.Forbidden:
            logger.warning("Bot tidak punya izin melakukan aksi '%s' di guild %s", action, guild.id)

        await self.service.log_violation(guild.id, member.id, rule, action, detail)

        config = await self.service.get_config(guild.id)
        if config.log_channel_id:
            log_channel = guild.get_channel(int(config.log_channel_id))
            if log_channel:
                desc = f"{member.mention} melanggar **{rule}**. Aksi: **{action}**."
                if detail:
                    desc += f"\nDetail: {detail}"
                try:
                    await log_channel.send(embed=JoyEmbed.warning(desc, title=f"{emoji.warning} Automod Triggered"))
                except discord.HTTPException:
                    pass

    async def _punish_raid_member(self, member: discord.Member, action: str) -> None:
        try:
            if action == "ban":
                await member.ban(reason="Anti Raid - Lonjakan member join terdeteksi")
            else:
                await member.kick(reason="Anti Raid - Lonjakan member join terdeteksi")
            await self.service.log_violation(member.guild.id, member.id, "Anti Raid", action)
        except discord.Forbidden:
            logger.warning("Bot tidak punya izin anti-raid action di guild %s", member.guild.id)

    # ================= LISTENERS =================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        config = await self.service.get_config(message.guild.id)

        if config.ghost_ping_enabled and (message.mentions or message.role_mentions or message.mention_everyone):
            self._track_mention_message(message.id, [m.id for m in message.mentions])

        if not config.enabled:
            return
        if await self._is_whitelisted(message):
            return

        content = message.content

        if config.scam_detection_enabled and looks_like_scam(content):
            await self._apply_message_action(message, config.scam_detection_action, config.spam_timeout_seconds, "Scam Detection")
            return

        if config.invite_filter_enabled and contains_invite(content):
            await self._apply_message_action(message, config.invite_filter_action, config.spam_timeout_seconds, "Invite Filter")
            return

        if config.link_filter_enabled and contains_link(content):
            await self._apply_message_action(message, config.link_filter_action, config.spam_timeout_seconds, "Link Filter")
            return

        if config.badword_filter_enabled:
            badwords = await self.service.get_badwords(message.guild.id)
            found = contains_badword(content, badwords) if badwords else None
            if found:
                await self._apply_message_action(
                    message, config.badword_action, config.spam_timeout_seconds, "Bad Word Filter", detail=f"kata: {found}"
                )
                return

        if config.caps_filter_enabled and is_excessive_caps(content, config.caps_filter_min_length, config.caps_filter_threshold_percent):
            await self._apply_message_action(message, config.caps_filter_action, config.spam_timeout_seconds, "Caps Filter")
            return

        if config.mention_spam_enabled:
            total_mentions = count_mentions(len(message.mentions), len(message.role_mentions), message.mention_everyone)
            if total_mentions >= config.mention_spam_threshold:
                await self._apply_message_action(
                    message, config.mention_spam_action, config.mention_spam_timeout_seconds, "Mention Spam / Mass Ping"
                )
                return

        if config.spam_enabled:
            is_spam = self._record_and_check_spam(
                message.guild.id, message.author.id, config.spam_message_threshold, config.spam_interval_seconds
            )
            if is_spam:
                await self._apply_message_action(message, config.spam_action, config.spam_timeout_seconds, "Spam Detection")
                return

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        config = await self.service.get_config(message.guild.id)
        if not config.ghost_ping_enabled or not config.log_channel_id:
            return

        tracked = self._mention_messages.pop(message.id, None)
        if tracked is None:
            return
        mentioned_ids, sent_at = tracked
        elapsed = time.time() - sent_at
        if elapsed > GHOST_PING_WINDOW_SECONDS or not mentioned_ids:
            return

        channel = message.guild.get_channel(int(config.log_channel_id))
        if channel is None:
            return
        mentions_str = ", ".join(f"<@{uid}>" for uid in mentioned_ids)
        try:
            await channel.send(embed=JoyEmbed.warning(
                f"{message.author.mention} kemungkinan **ghost ping** ke {mentions_str} di {message.channel.mention} "
                f"(pesan dihapus {elapsed:.0f} detik setelah dikirim).",
                title=f"{emoji.warning} Ghost Ping Terdeteksi",
            ))
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        config = await self.service.get_config(member.guild.id)
        if not config.anti_raid_enabled:
            return

        now = time.time()
        guild_id = member.guild.id

        lockdown_until = self._raid_lockdown_until.get(guild_id)
        if lockdown_until and now < lockdown_until:
            await self._punish_raid_member(member, config.anti_raid_action)
            return

        dq = self._join_times[guild_id]
        dq.append(now)
        while dq and now - dq[0] > config.anti_raid_interval_seconds:
            dq.popleft()

        if len(dq) >= config.anti_raid_join_threshold:
            self._raid_lockdown_until[guild_id] = now + config.anti_raid_lockdown_minutes * 60
            dq.clear()
            await self._punish_raid_member(member, config.anti_raid_action)

            if config.log_channel_id:
                channel = member.guild.get_channel(int(config.log_channel_id))
                if channel:
                    try:
                        await channel.send(embed=JoyEmbed.error(
                            f"Terdeteksi lonjakan member join (kemungkinan raid). Lockdown aktif "
                            f"selama {config.anti_raid_lockdown_minutes} menit — member baru otomatis di-**{config.anti_raid_action}**.",
                            title=f"{emoji.warning} Anti Raid Triggered",
                        ))
                    except discord.HTTPException:
                        pass

    # ================= PREFIX: !automod =================

    @commands.group(name="automod", invoke_without_command=True)
    @commands.guild_only()
    async def automod_prefix(self, ctx: commands.Context):
        config = await self.service.get_config(ctx.guild.id)
        await ctx.send(embed=self._settings_embed(config))

    def _settings_embed(self, config) -> discord.Embed:
        return JoyEmbed.info(
            f"**Status:** {'Aktif' if config.enabled else 'Nonaktif'}\n"
            f"**Log Channel:** {f'<#{config.log_channel_id}>' if config.log_channel_id else 'Belum diset'}\n\n"
            f"**Spam:** {'Aktif' if config.spam_enabled else 'Nonaktif'} ({config.spam_message_threshold} pesan/{config.spam_interval_seconds}s → {config.spam_action})\n"
            f"**Mention Spam:** {'Aktif' if config.mention_spam_enabled else 'Nonaktif'} ({config.mention_spam_threshold} mention → {config.mention_spam_action})\n"
            f"**Invite Filter:** {'Aktif' if config.invite_filter_enabled else 'Nonaktif'} ({config.invite_filter_action})\n"
            f"**Link Filter:** {'Aktif' if config.link_filter_enabled else 'Nonaktif'} ({config.link_filter_action})\n"
            f"**Caps Filter:** {'Aktif' if config.caps_filter_enabled else 'Nonaktif'} ({config.caps_filter_threshold_percent}%)\n"
            f"**Bad Word:** {'Aktif' if config.badword_filter_enabled else 'Nonaktif'} ({config.badword_action})\n"
            f"**Scam Detection:** {'Aktif' if config.scam_detection_enabled else 'Nonaktif'} ({config.scam_detection_action})\n"
            f"**Ghost Ping:** {'Aktif' if config.ghost_ping_enabled else 'Nonaktif'}\n"
            f"**Anti Raid:** {'Aktif' if config.anti_raid_enabled else 'Nonaktif'} ({config.anti_raid_join_threshold} join/{config.anti_raid_interval_seconds}s → {config.anti_raid_action})",
            title=f"{emoji.settings} Konfigurasi Auto Moderation",
        )

    @automod_prefix.command(name="toggle")
    @_manage_guild_prefix()
    async def automod_toggle(self, ctx: commands.Context, state: str):
        await self.service.set_config_field(ctx.guild.id, "enabled", int(state.lower() == "on"))
        await ctx.send(embed=JoyEmbed.success(f"Auto Moderation: **{state.upper()}**."))

    @automod_prefix.command(name="logchannel")
    @_manage_guild_prefix()
    async def automod_logchannel(self, ctx: commands.Context, channel: discord.TextChannel | None = None):
        await self.service.set_config_field(ctx.guild.id, "log_channel_id", str(channel.id) if channel else None)
        await ctx.send(embed=JoyEmbed.success(f"Log channel automod: {channel.mention if channel else 'dinonaktifkan'}."))

    @automod_prefix.command(name="spam")
    @_manage_guild_prefix()
    async def automod_spam(self, ctx: commands.Context, state: str, threshold: int = 5, interval: int = 5, action: str = "timeout"):
        if action not in VALID_ACTIONS:
            await ctx.send(embed=JoyEmbed.error(f"Aksi: {', '.join(VALID_ACTIONS)}"))
            return
        await self.service.set_config_field(ctx.guild.id, "spam_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(ctx.guild.id, "spam_message_threshold", threshold)
        await self.service.set_config_field(ctx.guild.id, "spam_interval_seconds", interval)
        await self.service.set_config_field(ctx.guild.id, "spam_action", action)
        await ctx.send(embed=JoyEmbed.success(f"Spam filter: **{state.upper()}** ({threshold} pesan/{interval}s → {action})."))

    @automod_prefix.command(name="mentionspam")
    @_manage_guild_prefix()
    async def automod_mentionspam(self, ctx: commands.Context, state: str, threshold: int = 5, action: str = "timeout"):
        if action not in VALID_ACTIONS:
            await ctx.send(embed=JoyEmbed.error(f"Aksi: {', '.join(VALID_ACTIONS)}"))
            return
        await self.service.set_config_field(ctx.guild.id, "mention_spam_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(ctx.guild.id, "mention_spam_threshold", threshold)
        await self.service.set_config_field(ctx.guild.id, "mention_spam_action", action)
        await ctx.send(embed=JoyEmbed.success(f"Mention Spam / Anti Mass Ping: **{state.upper()}** ({threshold} mention → {action})."))

    @automod_prefix.command(name="invitefilter")
    @_manage_guild_prefix()
    async def automod_invitefilter(self, ctx: commands.Context, state: str, action: str = "delete"):
        if action not in VALID_ACTIONS:
            await ctx.send(embed=JoyEmbed.error(f"Aksi: {', '.join(VALID_ACTIONS)}"))
            return
        await self.service.set_config_field(ctx.guild.id, "invite_filter_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(ctx.guild.id, "invite_filter_action", action)
        await ctx.send(embed=JoyEmbed.success(f"Invite Filter: **{state.upper()}** ({action})."))

    @automod_prefix.command(name="linkfilter")
    @_manage_guild_prefix()
    async def automod_linkfilter(self, ctx: commands.Context, state: str, action: str = "delete"):
        if action not in VALID_ACTIONS:
            await ctx.send(embed=JoyEmbed.error(f"Aksi: {', '.join(VALID_ACTIONS)}"))
            return
        await self.service.set_config_field(ctx.guild.id, "link_filter_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(ctx.guild.id, "link_filter_action", action)
        await ctx.send(embed=JoyEmbed.success(f"Link Filter: **{state.upper()}** ({action})."))

    @automod_prefix.command(name="capsfilter")
    @_manage_guild_prefix()
    async def automod_capsfilter(self, ctx: commands.Context, state: str, threshold_percent: int = 70, min_length: int = 10, action: str = "delete"):
        if action not in VALID_ACTIONS:
            await ctx.send(embed=JoyEmbed.error(f"Aksi: {', '.join(VALID_ACTIONS)}"))
            return
        await self.service.set_config_field(ctx.guild.id, "caps_filter_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(ctx.guild.id, "caps_filter_threshold_percent", threshold_percent)
        await self.service.set_config_field(ctx.guild.id, "caps_filter_min_length", min_length)
        await self.service.set_config_field(ctx.guild.id, "caps_filter_action", action)
        await ctx.send(embed=JoyEmbed.success(f"Caps Filter: **{state.upper()}** ({threshold_percent}%, min {min_length} karakter → {action})."))

    @automod_prefix.command(name="badword")
    @_manage_guild_prefix()
    async def automod_badword(self, ctx: commands.Context, state: str, action: str = "delete"):
        if action not in VALID_ACTIONS:
            await ctx.send(embed=JoyEmbed.error(f"Aksi: {', '.join(VALID_ACTIONS)}"))
            return
        await self.service.set_config_field(ctx.guild.id, "badword_filter_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(ctx.guild.id, "badword_action", action)
        await ctx.send(embed=JoyEmbed.success(f"Bad Word Filter: **{state.upper()}** ({action})."))

    @automod_prefix.command(name="addbadword")
    @_manage_guild_prefix()
    async def automod_addbadword(self, ctx: commands.Context, *, word: str):
        await self.service.add_badword(ctx.guild.id, word)
        await ctx.send(embed=JoyEmbed.success(f"Kata `{word}` ditambahkan ke bad word list."))

    @automod_prefix.command(name="removebadword")
    @_manage_guild_prefix()
    async def automod_removebadword(self, ctx: commands.Context, *, word: str):
        await self.service.remove_badword(ctx.guild.id, word)
        await ctx.send(embed=JoyEmbed.success(f"Kata `{word}` dihapus dari bad word list."))

    @automod_prefix.command(name="badwordlist")
    async def automod_badwordlist(self, ctx: commands.Context):
        words = await self.service.get_badwords(ctx.guild.id)
        text = ", ".join(f"`{w}`" for w in words) if words else "Belum ada kata terlarang."
        await ctx.send(embed=JoyEmbed.info(text, title=f"{emoji.settings} Bad Word List"))

    @automod_prefix.command(name="scamdetection")
    @_manage_guild_prefix()
    async def automod_scamdetection(self, ctx: commands.Context, state: str, action: str = "ban"):
        if action not in VALID_ACTIONS:
            await ctx.send(embed=JoyEmbed.error(f"Aksi: {', '.join(VALID_ACTIONS)}"))
            return
        await self.service.set_config_field(ctx.guild.id, "scam_detection_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(ctx.guild.id, "scam_detection_action", action)
        await ctx.send(embed=JoyEmbed.success(f"Scam Detection: **{state.upper()}** ({action})."))

    @automod_prefix.command(name="ghostping")
    @_manage_guild_prefix()
    async def automod_ghostping(self, ctx: commands.Context, state: str):
        await self.service.set_config_field(ctx.guild.id, "ghost_ping_enabled", int(state.lower() == "on"))
        await ctx.send(embed=JoyEmbed.success(f"Anti Ghost Ping: **{state.upper()}**."))

    @automod_prefix.command(name="antiraid")
    @_manage_guild_prefix()
    async def automod_antiraid(self, ctx: commands.Context, state: str, threshold: int = 10, interval: int = 10, action: str = "kick"):
        if action not in ("kick", "ban"):
            await ctx.send(embed=JoyEmbed.error("Aksi: kick atau ban"))
            return
        await self.service.set_config_field(ctx.guild.id, "anti_raid_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(ctx.guild.id, "anti_raid_join_threshold", threshold)
        await self.service.set_config_field(ctx.guild.id, "anti_raid_interval_seconds", interval)
        await self.service.set_config_field(ctx.guild.id, "anti_raid_action", action)
        await ctx.send(embed=JoyEmbed.success(f"Anti Raid / Anti Join Flood: **{state.upper()}** ({threshold} join/{interval}s → {action})."))

    @automod_prefix.command(name="whitelist")
    @_manage_guild_prefix()
    async def automod_whitelist(self, ctx: commands.Context, action: str, target_type: str, target: discord.Member | discord.Role | discord.TextChannel):
        target_type = target_type.lower()
        if target_type not in ("user", "role", "channel"):
            await ctx.send(embed=JoyEmbed.error("Tipe: user, role, atau channel"))
            return
        if action.lower() == "add":
            await self.service.add_to_whitelist(ctx.guild.id, target_type, target.id)
            await ctx.send(embed=JoyEmbed.success(f"{target.mention} ditambahkan ke whitelist automod."))
        elif action.lower() == "remove":
            await self.service.remove_from_whitelist(ctx.guild.id, target_type, target.id)
            await ctx.send(embed=JoyEmbed.success(f"{target.mention} dihapus dari whitelist automod."))
        else:
            await ctx.send(embed=JoyEmbed.error("Gunakan `add` atau `remove`."))

    @automod_prefix.command(name="settings")
    async def automod_settings(self, ctx: commands.Context):
        config = await self.service.get_config(ctx.guild.id)
        await ctx.send(embed=self._settings_embed(config))

    # ================= SLASH: /automod =================

    @app_commands.command(name="settings", description="Menampilkan konfigurasi auto moderation.")
    async def automod_settings_slash(self, interaction: discord.Interaction):
        config = await self.service.get_config(interaction.guild_id)
        await interaction.response.send_message(embed=self._settings_embed(config))

    @app_commands.command(name="toggle", description="Aktifkan/nonaktifkan auto moderation.")
    @_manage_guild_slash()
    async def automod_toggle_slash(self, interaction: discord.Interaction, state: str):
        await self.service.set_config_field(interaction.guild_id, "enabled", int(state.lower() == "on"))
        await interaction.response.send_message(embed=JoyEmbed.success(f"Auto Moderation: **{state.upper()}**."))

    @app_commands.command(name="logchannel", description="Set channel log untuk automod.")
    @_manage_guild_slash()
    async def automod_logchannel_slash(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None):
        await self.service.set_config_field(interaction.guild_id, "log_channel_id", str(channel.id) if channel else None)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Log channel automod: {channel.mention if channel else 'dinonaktifkan'}."))

    @app_commands.command(name="spam", description="Konfigurasi Spam Filter.")
    @app_commands.choices(action=[app_commands.Choice(name=a, value=a) for a in VALID_ACTIONS])
    @_manage_guild_slash()
    async def automod_spam_slash(self, interaction: discord.Interaction, state: str, threshold: int = 5, interval: int = 5, action: app_commands.Choice[str] | None = None):
        act = action.value if action else "timeout"
        await self.service.set_config_field(interaction.guild_id, "spam_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(interaction.guild_id, "spam_message_threshold", threshold)
        await self.service.set_config_field(interaction.guild_id, "spam_interval_seconds", interval)
        await self.service.set_config_field(interaction.guild_id, "spam_action", act)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Spam filter: **{state.upper()}** ({threshold} pesan/{interval}s → {act})."))

    @app_commands.command(name="mentionspam", description="Konfigurasi Mention Spam / Anti Mass Ping.")
    @app_commands.choices(action=[app_commands.Choice(name=a, value=a) for a in VALID_ACTIONS])
    @_manage_guild_slash()
    async def automod_mentionspam_slash(self, interaction: discord.Interaction, state: str, threshold: int = 5, action: app_commands.Choice[str] | None = None):
        act = action.value if action else "timeout"
        await self.service.set_config_field(interaction.guild_id, "mention_spam_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(interaction.guild_id, "mention_spam_threshold", threshold)
        await self.service.set_config_field(interaction.guild_id, "mention_spam_action", act)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Mention Spam / Anti Mass Ping: **{state.upper()}** ({threshold} mention → {act})."))

    @app_commands.command(name="invitefilter", description="Konfigurasi Invite Filter.")
    @app_commands.choices(action=[app_commands.Choice(name=a, value=a) for a in VALID_ACTIONS])
    @_manage_guild_slash()
    async def automod_invitefilter_slash(self, interaction: discord.Interaction, state: str, action: app_commands.Choice[str] | None = None):
        act = action.value if action else "delete"
        await self.service.set_config_field(interaction.guild_id, "invite_filter_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(interaction.guild_id, "invite_filter_action", act)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Invite Filter: **{state.upper()}** ({act})."))

    @app_commands.command(name="linkfilter", description="Konfigurasi Link Filter.")
    @app_commands.choices(action=[app_commands.Choice(name=a, value=a) for a in VALID_ACTIONS])
    @_manage_guild_slash()
    async def automod_linkfilter_slash(self, interaction: discord.Interaction, state: str, action: app_commands.Choice[str] | None = None):
        act = action.value if action else "delete"
        await self.service.set_config_field(interaction.guild_id, "link_filter_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(interaction.guild_id, "link_filter_action", act)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Link Filter: **{state.upper()}** ({act})."))

    @app_commands.command(name="capsfilter", description="Konfigurasi Caps Filter.")
    @app_commands.choices(action=[app_commands.Choice(name=a, value=a) for a in VALID_ACTIONS])
    @_manage_guild_slash()
    async def automod_capsfilter_slash(self, interaction: discord.Interaction, state: str, threshold_percent: int = 70, min_length: int = 10, action: app_commands.Choice[str] | None = None):
        act = action.value if action else "delete"
        await self.service.set_config_field(interaction.guild_id, "caps_filter_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(interaction.guild_id, "caps_filter_threshold_percent", threshold_percent)
        await self.service.set_config_field(interaction.guild_id, "caps_filter_min_length", min_length)
        await self.service.set_config_field(interaction.guild_id, "caps_filter_action", act)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Caps Filter: **{state.upper()}** ({threshold_percent}%, min {min_length} karakter → {act})."))

    @app_commands.command(name="badword", description="Konfigurasi Bad Word Filter.")
    @app_commands.choices(action=[app_commands.Choice(name=a, value=a) for a in VALID_ACTIONS])
    @_manage_guild_slash()
    async def automod_badword_slash(self, interaction: discord.Interaction, state: str, action: app_commands.Choice[str] | None = None):
        act = action.value if action else "delete"
        await self.service.set_config_field(interaction.guild_id, "badword_filter_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(interaction.guild_id, "badword_action", act)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Bad Word Filter: **{state.upper()}** ({act})."))

    @app_commands.command(name="addbadword", description="Tambah kata ke bad word list.")
    @_manage_guild_slash()
    async def automod_addbadword_slash(self, interaction: discord.Interaction, word: str):
        await self.service.add_badword(interaction.guild_id, word)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Kata `{word}` ditambahkan ke bad word list."))

    @app_commands.command(name="removebadword", description="Hapus kata dari bad word list.")
    @_manage_guild_slash()
    async def automod_removebadword_slash(self, interaction: discord.Interaction, word: str):
        await self.service.remove_badword(interaction.guild_id, word)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Kata `{word}` dihapus dari bad word list."))

    @app_commands.command(name="badwordlist", description="Menampilkan bad word list.")
    async def automod_badwordlist_slash(self, interaction: discord.Interaction):
        words = await self.service.get_badwords(interaction.guild_id)
        text = ", ".join(f"`{w}`" for w in words) if words else "Belum ada kata terlarang."
        await interaction.response.send_message(embed=JoyEmbed.info(text, title=f"{emoji.settings} Bad Word List"), ephemeral=True)

    @app_commands.command(name="scamdetection", description="Konfigurasi Scam Detection.")
    @app_commands.choices(action=[app_commands.Choice(name=a, value=a) for a in VALID_ACTIONS])
    @_manage_guild_slash()
    async def automod_scamdetection_slash(self, interaction: discord.Interaction, state: str, action: app_commands.Choice[str] | None = None):
        act = action.value if action else "ban"
        await self.service.set_config_field(interaction.guild_id, "scam_detection_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(interaction.guild_id, "scam_detection_action", act)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Scam Detection: **{state.upper()}** ({act})."))

    @app_commands.command(name="ghostping", description="Toggle Anti Ghost Ping.")
    @_manage_guild_slash()
    async def automod_ghostping_slash(self, interaction: discord.Interaction, state: str):
        await self.service.set_config_field(interaction.guild_id, "ghost_ping_enabled", int(state.lower() == "on"))
        await interaction.response.send_message(embed=JoyEmbed.success(f"Anti Ghost Ping: **{state.upper()}**."))

    @app_commands.command(name="antiraid", description="Konfigurasi Anti Raid / Anti Join Flood.")
    @app_commands.choices(action=[app_commands.Choice(name=a, value=a) for a in ("kick", "ban")])
    @_manage_guild_slash()
    async def automod_antiraid_slash(self, interaction: discord.Interaction, state: str, threshold: int = 10, interval: int = 10, action: app_commands.Choice[str] | None = None):
        act = action.value if action else "kick"
        await self.service.set_config_field(interaction.guild_id, "anti_raid_enabled", int(state.lower() == "on"))
        await self.service.set_config_field(interaction.guild_id, "anti_raid_join_threshold", threshold)
        await self.service.set_config_field(interaction.guild_id, "anti_raid_interval_seconds", interval)
        await self.service.set_config_field(interaction.guild_id, "anti_raid_action", act)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Anti Raid / Anti Join Flood: **{state.upper()}** ({threshold} join/{interval}s → {act})."))

    @app_commands.command(name="whitelistadd", description="Tambah user/role/channel ke whitelist automod.")
    @app_commands.choices(target_type=[app_commands.Choice(name=t, value=t) for t in ("user", "role", "channel")])
    @_manage_guild_slash()
    async def automod_whitelistadd_slash(self, interaction: discord.Interaction, target_type: app_commands.Choice[str], user: discord.Member | None = None, role: discord.Role | None = None, channel: discord.TextChannel | None = None):
        target = user or role or channel
        if target is None:
            await interaction.response.send_message(embed=JoyEmbed.error("Isi salah satu: user, role, atau channel."), ephemeral=True)
            return
        await self.service.add_to_whitelist(interaction.guild_id, target_type.value, target.id)
        await interaction.response.send_message(embed=JoyEmbed.success(f"{target.mention} ditambahkan ke whitelist automod."))

    @app_commands.command(name="whitelistremove", description="Hapus user/role/channel dari whitelist automod.")
    @app_commands.choices(target_type=[app_commands.Choice(name=t, value=t) for t in ("user", "role", "channel")])
    @_manage_guild_slash()
    async def automod_whitelistremove_slash(self, interaction: discord.Interaction, target_type: app_commands.Choice[str], user: discord.Member | None = None, role: discord.Role | None = None, channel: discord.TextChannel | None = None):
        target = user or role or channel
        if target is None:
            await interaction.response.send_message(embed=JoyEmbed.error("Isi salah satu: user, role, atau channel."), ephemeral=True)
            return
        await self.service.remove_from_whitelist(interaction.guild_id, target_type.value, target.id)
        await interaction.response.send_message(embed=JoyEmbed.success(f"{target.mention} dihapus dari whitelist automod."))


async def setup(bot: JoyUniverse):
    await bot.add_cog(AutoMod(bot))
