"""
Cog Roles untuk JOY UNIVERSE (Stage 5): Auto Role & Reaction Role.

Auto Role  : role otomatis untuk member baru (multi role didukung).
Reaction Role: 3 tipe panel (Button, Reaction emoji, Dropdown/Select),
               dengan Unique Mode (radio-button, cuma 1 role per panel)
               dan Verification Mode (role cuma ditambah, tidak pernah dilepas).
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.bot import JoyUniverse
from bot.core.config import config as bot_config
from bot.services.auto_role_service import AutoRoleService
from bot.services.reaction_role_service import VALID_STYLES, ReactionRoleService
from bot.utils.embeds import JoyEmbed
from bot.utils.emojis import emoji
from bot.utils.reaction_role_views import build_button_view, build_dropdown_view

logger = logging.getLogger("joyuniverse.cogs.roles")

PANEL_TYPE_CHOICES = ["button", "reaction", "dropdown"]


def _manage_roles_prefix():
    return commands.has_permissions(manage_roles=True)


def _manage_roles_slash():
    return app_commands.checks.has_permissions(manage_roles=True)


class Roles(commands.Cog):
    """Prefix: `!autorole ...`, `!reactionrole ...` (alias `!rr`). Slash: `/autorole ...`, `/reactionrole ...`."""

    autorole_group = app_commands.Group(name="autorole", description="Kelola auto role untuk member baru.")
    reactionrole_group = app_commands.Group(name="reactionrole", description="Kelola panel reaction role.")

    def __init__(self, bot: JoyUniverse):
        self.bot = bot
        self.auto_role_service = AutoRoleService(bot.db)
        self.rr_service = ReactionRoleService(bot.db)

    # ================= AUTO ROLE: EVENT =================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            if not await self.auto_role_service.is_enabled(member.guild.id):
                return
            role_ids = await self.auto_role_service.list_roles(member.guild.id)
            if not role_ids:
                return
            roles = [member.guild.get_role(int(rid)) for rid in role_ids]
            roles = [r for r in roles if r is not None]
            if roles:
                await member.add_roles(*roles, reason="Auto Role")
        except discord.Forbidden:
            logger.warning("Bot tidak punya izin memberi auto role di guild %s", member.guild.id)
        except Exception:
            logger.exception("Gagal memberi auto role di guild %s", member.guild.id)

    # ================= AUTO ROLE: PREFIX =================

    @commands.group(name="autorole", invoke_without_command=True)
    @commands.guild_only()
    async def autorole_prefix(self, ctx: commands.Context):
        """Menampilkan status dan daftar auto role."""
        enabled = await self.auto_role_service.is_enabled(ctx.guild.id)
        role_ids = await self.auto_role_service.list_roles(ctx.guild.id)
        role_mentions = ", ".join(f"<@&{rid}>" for rid in role_ids) if role_ids else "Belum ada role."
        await ctx.send(embed=JoyEmbed.info(
            f"**Status:** {'Aktif' if enabled else 'Nonaktif'}\n**Role:** {role_mentions}",
            title=f"{emoji.settings} Auto Role",
        ))

    @autorole_prefix.command(name="toggle")
    @_manage_roles_prefix()
    async def autorole_toggle(self, ctx: commands.Context, state: str):
        """Aktifkan atau nonaktifkan auto role."""
        await self.auto_role_service.set_enabled(ctx.guild.id, state.lower() == "on")
        await ctx.send(embed=JoyEmbed.success(f"Auto role: **{state.upper()}**."))

    @autorole_prefix.command(name="add")
    @_manage_roles_prefix()
    async def autorole_add(self, ctx: commands.Context, role: discord.Role):
        """Tambahkan role ke daftar auto role."""
        await self.auto_role_service.add_role(ctx.guild.id, role.id)
        await ctx.send(embed=JoyEmbed.success(f"{role.mention} ditambahkan ke auto role."))

    @autorole_prefix.command(name="remove")
    @_manage_roles_prefix()
    async def autorole_remove(self, ctx: commands.Context, role: discord.Role):
        """Hapus role dari daftar auto role."""
        await self.auto_role_service.remove_role(ctx.guild.id, role.id)
        await ctx.send(embed=JoyEmbed.success(f"{role.mention} dihapus dari auto role."))

    @autorole_prefix.command(name="list")
    async def autorole_list(self, ctx: commands.Context):
        """Menampilkan daftar auto role."""
        role_ids = await self.auto_role_service.list_roles(ctx.guild.id)
        role_mentions = "\n".join(f"<@&{rid}>" for rid in role_ids) if role_ids else "Belum ada auto role."
        await ctx.send(embed=JoyEmbed.info(role_mentions, title=f"{emoji.settings} Daftar Auto Role"))

    # ================= AUTO ROLE: SLASH =================

    @autorole_group.command(name="settings", description="Menampilkan konfigurasi auto role.")
    async def autorole_settings_slash(self, interaction: discord.Interaction):
        enabled = await self.auto_role_service.is_enabled(interaction.guild_id)
        role_ids = await self.auto_role_service.list_roles(interaction.guild_id)
        role_mentions = ", ".join(f"<@&{rid}>" for rid in role_ids) if role_ids else "Belum ada role."
        await interaction.response.send_message(embed=JoyEmbed.info(
            f"**Status:** {'Aktif' if enabled else 'Nonaktif'}\n**Role:** {role_mentions}",
            title=f"{emoji.settings} Auto Role",
        ))

    @autorole_group.command(name="toggle", description="Aktifkan/nonaktifkan auto role.")
    @_manage_roles_slash()
    async def autorole_toggle_slash(self, interaction: discord.Interaction, state: str):
        await self.auto_role_service.set_enabled(interaction.guild_id, state.lower() == "on")
        await interaction.response.send_message(embed=JoyEmbed.success(f"Auto role: **{state.upper()}**."))

    @autorole_group.command(name="add", description="Tambah role ke auto role.")
    @_manage_roles_slash()
    async def autorole_add_slash(self, interaction: discord.Interaction, role: discord.Role):
        await self.auto_role_service.add_role(interaction.guild_id, role.id)
        await interaction.response.send_message(embed=JoyEmbed.success(f"{role.mention} ditambahkan ke auto role."))

    @autorole_group.command(name="remove", description="Hapus role dari auto role.")
    @_manage_roles_slash()
    async def autorole_remove_slash(self, interaction: discord.Interaction, role: discord.Role):
        await self.auto_role_service.remove_role(interaction.guild_id, role.id)
        await interaction.response.send_message(embed=JoyEmbed.success(f"{role.mention} dihapus dari auto role."))

    @autorole_group.command(name="list", description="Menampilkan daftar auto role.")
    async def autorole_list_slash(self, interaction: discord.Interaction):
        role_ids = await self.auto_role_service.list_roles(interaction.guild_id)
        role_mentions = "\n".join(f"<@&{rid}>" for rid in role_ids) if role_ids else "Belum ada auto role."
        await interaction.response.send_message(embed=JoyEmbed.info(role_mentions, title=f"{emoji.settings} Daftar Auto Role"))

    # ================= REACTION ROLE: HELPERS =================

    def _panel_embed(self, panel) -> discord.Embed:
        color = int(panel.color.lstrip("#"), 16) if panel.color else bot_config.default_color
        return JoyEmbed(title=panel.title, description=panel.description, color=color)

    async def _post_panel(self, panel, channel: discord.TextChannel) -> discord.Message:
        entries = await self.rr_service.get_entries(panel.id)
        embed = self._panel_embed(panel)

        if panel.panel_type == "reaction":
            lines = [f"{e.emoji} → <@&{e.role_id}>" for e in entries]
            if lines:
                base_desc = embed.description or ""
                embed.description = (base_desc + "\n\n" if base_desc else "") + "\n".join(lines)
            message = await channel.send(embed=embed)
            for e in entries:
                if e.emoji:
                    try:
                        await message.add_reaction(e.emoji)
                    except discord.HTTPException:
                        logger.warning("Gagal menambah reaction '%s' di panel #%s", e.emoji, panel.id)
        elif panel.panel_type == "button":
            view = build_button_view(entries)
            message = await channel.send(embed=embed, view=view)
        else:  # dropdown
            view = build_dropdown_view(panel.id, entries, panel.unique_mode)
            message = await channel.send(embed=embed, view=view)

        await self.rr_service.set_message_id(panel.id, channel.id, message.id)
        return message

    # ================= REACTION ROLE: INTERACTION HANDLER =================

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        custom_id = (interaction.data or {}).get("custom_id", "")
        if not custom_id.startswith("joyrr:"):
            return

        parts = custom_id.split(":")
        if len(parts) < 3:
            return
        kind = parts[1]

        try:
            if kind == "btn":
                await self._handle_button_click(interaction, int(parts[2]))
            elif kind == "dd":
                selected_ids = [int(v) for v in interaction.data.get("values", [])]
                await self._handle_dropdown_select(interaction, int(parts[2]), selected_ids)
        except Exception:
            logger.exception("Error saat memproses reaction role interaction")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=JoyEmbed.error("Terjadi kesalahan saat memproses role."), ephemeral=True
                )

    async def _handle_button_click(self, interaction: discord.Interaction, entry_id: int) -> None:
        entry = await self.rr_service.get_entry_by_id(entry_id)
        if entry is None:
            await interaction.response.send_message(embed=JoyEmbed.error("Role ini sudah tidak tersedia."), ephemeral=True)
            return

        panel = await self.rr_service.get_panel(entry.panel_id, interaction.guild_id)
        if panel is None:
            await interaction.response.send_message(embed=JoyEmbed.error("Panel tidak ditemukan."), ephemeral=True)
            return

        guild = interaction.guild
        member = interaction.user
        role = guild.get_role(int(entry.role_id))
        if role is None:
            await interaction.response.send_message(embed=JoyEmbed.error("Role sudah dihapus dari server."), ephemeral=True)
            return

        if panel.verification_mode:
            if role in member.roles:
                await interaction.response.send_message(embed=JoyEmbed.info("Kamu sudah terverifikasi."), ephemeral=True)
            else:
                await member.add_roles(role, reason="Reaction Role - Verification")
                await interaction.response.send_message(embed=JoyEmbed.success(f"Kamu mendapat role {role.mention}!"), ephemeral=True)
            return

        if panel.unique_mode:
            other_entries = [e for e in await self.rr_service.get_entries(panel.id) if e.id != entry.id]
            other_roles = [guild.get_role(int(e.role_id)) for e in other_entries]
            to_remove = [r for r in other_roles if r and r in member.roles]
            if to_remove:
                await member.remove_roles(*to_remove, reason="Reaction Role - Unique mode")

        if role in member.roles:
            await member.remove_roles(role, reason="Reaction Role - Toggle off")
            await interaction.response.send_message(embed=JoyEmbed.info(f"Role {role.mention} dihapus."), ephemeral=True)
        else:
            await member.add_roles(role, reason="Reaction Role - Toggle on")
            await interaction.response.send_message(embed=JoyEmbed.success(f"Kamu mendapat role {role.mention}!"), ephemeral=True)

    async def _handle_dropdown_select(self, interaction: discord.Interaction, panel_id: int, selected_entry_ids: list[int]) -> None:
        panel = await self.rr_service.get_panel(panel_id, interaction.guild_id)
        if panel is None:
            await interaction.response.send_message(embed=JoyEmbed.error("Panel tidak ditemukan."), ephemeral=True)
            return

        guild = interaction.guild
        member = interaction.user
        entries = await self.rr_service.get_entries(panel_id)

        selected_role_ids = {e.role_id for e in entries if e.id in selected_entry_ids}

        to_add, to_remove = [], []
        for e in entries:
            role = guild.get_role(int(e.role_id))
            if role is None:
                continue
            has_role = role in member.roles
            wants_role = e.role_id in selected_role_ids
            if wants_role and not has_role:
                to_add.append(role)
            elif not wants_role and has_role and not panel.verification_mode:
                to_remove.append(role)

        if to_add:
            await member.add_roles(*to_add, reason="Reaction Role - Dropdown")
        if to_remove:
            await member.remove_roles(*to_remove, reason="Reaction Role - Dropdown")

        await interaction.response.send_message(embed=JoyEmbed.success("Role kamu sudah diperbarui!"), ephemeral=True)

    # ================= REACTION ROLE: RAW REACTION EVENTS =================

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member is None or payload.member.bot:
            return
        panel = await self.rr_service.get_panel_by_message(payload.message_id)
        if panel is None or panel.panel_type != "reaction":
            return

        entries = await self.rr_service.get_entries(panel.id)
        emoji_str = str(payload.emoji)
        entry = next((e for e in entries if e.emoji == emoji_str), None)
        if entry is None:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        role = guild.get_role(int(entry.role_id))
        if role is None:
            return
        member = payload.member

        try:
            if panel.unique_mode and not panel.verification_mode:
                other_roles = [guild.get_role(int(e.role_id)) for e in entries if e.id != entry.id]
                to_remove = [r for r in other_roles if r and r in member.roles]
                if to_remove:
                    await member.remove_roles(*to_remove, reason="Reaction Role - Unique mode")
            if role not in member.roles:
                await member.add_roles(role, reason="Reaction Role")
        except discord.Forbidden:
            logger.warning("Bot tidak punya izin memberi reaction role di guild %s", guild.id)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        panel = await self.rr_service.get_panel_by_message(payload.message_id)
        if panel is None or panel.panel_type != "reaction" or panel.verification_mode:
            return

        entries = await self.rr_service.get_entries(panel.id)
        emoji_str = str(payload.emoji)
        entry = next((e for e in entries if e.emoji == emoji_str), None)
        if entry is None:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        member = guild.get_member(payload.user_id)
        if member is None or member.bot:
            return
        role = guild.get_role(int(entry.role_id))
        if role is None:
            return

        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Reaction Role - Reaksi dihapus")
        except discord.Forbidden:
            logger.warning("Bot tidak punya izin melepas reaction role di guild %s", guild.id)

    # ================= REACTION ROLE: PREFIX =================

    @commands.group(name="reactionrole", aliases=["rr"], invoke_without_command=True)
    @commands.guild_only()
    async def rr_prefix(self, ctx: commands.Context):
        """Menampilkan daftar panel reaction role."""
        await self._send_panel_list(ctx)

    @rr_prefix.command(name="create")
    @_manage_roles_prefix()
    async def rr_create(self, ctx: commands.Context, panel_type: str, title: str, *, description: str = ""):
        """Membuat panel reaction role baru."""
        panel_type = panel_type.lower()
        if panel_type not in PANEL_TYPE_CHOICES:
            await ctx.send(embed=JoyEmbed.error(f"Tipe panel: {', '.join(PANEL_TYPE_CHOICES)}"))
            return
        panel_id = await self.rr_service.create_panel(
            guild_id=ctx.guild.id, panel_type=panel_type, title=title,
            description=description or None, color=None, created_by=ctx.author.id,
        )
        await ctx.send(embed=JoyEmbed.success(
            f"Panel **{title}** (ID `{panel_id}`, tipe `{panel_type}`) dibuat. "
            f"Tambahkan role dengan `!reactionrole addrole {panel_id} @role emoji`."
        ))

    @rr_prefix.command(name="addrole")
    @_manage_roles_prefix()
    async def rr_addrole(
        self, ctx: commands.Context, panel_id: int, role: discord.Role,
        emoji_or_label: str, label: str = "", style: str = "secondary", *, description: str = "",
    ):
        """Tambahkan role ke panel reaction role."""
        panel = await self.rr_service.get_panel(panel_id, ctx.guild.id)
        if panel is None:
            await ctx.send(embed=JoyEmbed.error("Panel tidak ditemukan."))
            return
        style = style.lower() if style.lower() in VALID_STYLES else "secondary"

        emoji_value = emoji_or_label if panel.panel_type in ("reaction", "button") else None
        label_value = label or (emoji_or_label if panel.panel_type == "dropdown" else role.name)

        entry_id = await self.rr_service.add_entry(
            panel_id=panel_id, role_id=role.id,
            emoji=emoji_value if panel.panel_type != "dropdown" else (emoji_or_label if label else None),
            label=label_value, style=style, description=description or None,
        )
        await ctx.send(embed=JoyEmbed.success(f"Role {role.mention} ditambahkan ke panel #{panel_id} (entry `{entry_id}`)."))

    @rr_prefix.command(name="removerole")
    @_manage_roles_prefix()
    async def rr_removerole(self, ctx: commands.Context, entry_id: int):
        """Hapus satu entry role dari panel."""
        ok = await self.rr_service.remove_entry(entry_id)
        await ctx.send(embed=JoyEmbed.success("Entry dihapus.") if ok else JoyEmbed.error("Entry tidak ditemukan."))

    @rr_prefix.command(name="post")
    @_manage_roles_prefix()
    async def rr_post(self, ctx: commands.Context, panel_id: int, channel: discord.TextChannel):
        """Kirim/post panel reaction role ke sebuah channel."""
        panel = await self.rr_service.get_panel(panel_id, ctx.guild.id)
        if panel is None:
            await ctx.send(embed=JoyEmbed.error("Panel tidak ditemukan."))
            return
        entries = await self.rr_service.get_entries(panel_id)
        if not entries:
            await ctx.send(embed=JoyEmbed.error("Panel belum punya role. Tambahkan dulu dengan `addrole`."))
            return
        await self._post_panel(panel, channel)
        await ctx.send(embed=JoyEmbed.success(f"Panel berhasil di-post di {channel.mention}."))

    @rr_prefix.command(name="delete")
    @_manage_roles_prefix()
    async def rr_delete(self, ctx: commands.Context, panel_id: int):
        """Hapus panel reaction role."""
        ok = await self.rr_service.delete_panel(panel_id, ctx.guild.id)
        await ctx.send(embed=JoyEmbed.success(f"Panel #{panel_id} dihapus.") if ok else JoyEmbed.error("Panel tidak ditemukan."))

    @rr_prefix.command(name="list")
    async def rr_list(self, ctx: commands.Context):
        """Menampilkan daftar panel reaction role."""
        await self._send_panel_list(ctx)

    @rr_prefix.command(name="info")
    async def rr_info(self, ctx: commands.Context, panel_id: int):
        """Menampilkan detail sebuah panel reaction role."""
        await self._send_panel_info(ctx, panel_id)

    @rr_prefix.command(name="unique")
    @_manage_roles_prefix()
    async def rr_unique(self, ctx: commands.Context, panel_id: int, state: str):
        """Atur unique mode (cuma boleh 1 role) untuk panel."""
        ok = await self.rr_service.set_panel_flag(panel_id, ctx.guild.id, "unique_mode", state.lower() == "on")
        await ctx.send(embed=JoyEmbed.success(f"Unique mode: **{state.upper()}**.") if ok else JoyEmbed.error("Panel tidak ditemukan."))

    @rr_prefix.command(name="verification")
    @_manage_roles_prefix()
    async def rr_verification(self, ctx: commands.Context, panel_id: int, state: str):
        """Atur verification mode (role cuma ditambah, tidak pernah dilepas) untuk panel."""
        ok = await self.rr_service.set_panel_flag(panel_id, ctx.guild.id, "verification_mode", state.lower() == "on")
        await ctx.send(embed=JoyEmbed.success(f"Verification mode: **{state.upper()}**.") if ok else JoyEmbed.error("Panel tidak ditemukan."))

    async def _send_panel_list(self, ctx: commands.Context) -> None:
        panels = await self.rr_service.list_panels(ctx.guild.id)
        if not panels:
            await ctx.send(embed=JoyEmbed.info("Belum ada panel reaction role."))
            return
        lines = [
            f"`#{p.id}` **{p.title}** — tipe `{p.panel_type}`"
            + (" • Unique" if p.unique_mode else "")
            + (" • Verification" if p.verification_mode else "")
            + (f" • posted <#{p.channel_id}>" if p.channel_id else " • belum di-post")
            for p in panels
        ]
        await ctx.send(embed=JoyEmbed.info("\n".join(lines), title=f"{emoji.settings} Daftar Panel Reaction Role"))

    async def _send_panel_info(self, ctx: commands.Context, panel_id: int) -> None:
        panel = await self.rr_service.get_panel(panel_id, ctx.guild.id)
        if panel is None:
            await ctx.send(embed=JoyEmbed.error("Panel tidak ditemukan."))
            return
        entries = await self.rr_service.get_entries(panel_id)
        lines = [f"`{e.id}` {e.emoji or ''} <@&{e.role_id}> — {e.label or '-'}" for e in entries]
        await ctx.send(embed=JoyEmbed.info(
            f"**Tipe:** {panel.panel_type}\n"
            f"**Unique Mode:** {'Ya' if panel.unique_mode else 'Tidak'}\n"
            f"**Verification Mode:** {'Ya' if panel.verification_mode else 'Tidak'}\n"
            f"**Status:** {'Posted di <#' + panel.channel_id + '>' if panel.channel_id else 'Belum di-post'}\n\n"
            f"**Entries:**\n" + ("\n".join(lines) if lines else "Belum ada role."),
            title=f"{emoji.info} Panel #{panel.id} — {panel.title}",
        ))

    # ================= REACTION ROLE: SLASH =================

    @reactionrole_group.command(name="create", description="Membuat panel reaction role baru.")
    @app_commands.choices(panel_type=[app_commands.Choice(name=t, value=t) for t in PANEL_TYPE_CHOICES])
    @_manage_roles_slash()
    async def rr_create_slash(
        self, interaction: discord.Interaction, panel_type: app_commands.Choice[str],
        title: str, description: str | None = None, color: str | None = None,
        unique_mode: bool = False, verification_mode: bool = False,
    ):
        if color:
            try:
                int(color.lstrip("#"), 16)
            except ValueError:
                await interaction.response.send_message(embed=JoyEmbed.error("Format warna tidak valid."), ephemeral=True)
                return
        panel_id = await self.rr_service.create_panel(
            guild_id=interaction.guild_id, panel_type=panel_type.value, title=title,
            description=description, color=color, created_by=interaction.user.id,
            unique_mode=unique_mode, verification_mode=verification_mode,
        )
        await interaction.response.send_message(embed=JoyEmbed.success(
            f"Panel **{title}** (ID `{panel_id}`) dibuat. Tambahkan role dengan `/reactionrole addrole`."
        ))

    @reactionrole_group.command(name="addrole", description="Tambah role ke panel reaction role.")
    @app_commands.choices(style=[app_commands.Choice(name=s, value=s) for s in VALID_STYLES])
    @_manage_roles_slash()
    async def rr_addrole_slash(
        self, interaction: discord.Interaction, panel_id: int, role: discord.Role,
        label: str | None = None, emoji_str: str | None = None,
        style: app_commands.Choice[str] | None = None, description: str | None = None,
    ):
        panel = await self.rr_service.get_panel(panel_id, interaction.guild_id)
        if panel is None:
            await interaction.response.send_message(embed=JoyEmbed.error("Panel tidak ditemukan."), ephemeral=True)
            return
        entry_id = await self.rr_service.add_entry(
            panel_id=panel_id, role_id=role.id, emoji=emoji_str,
            label=label or role.name, style=style.value if style else "secondary",
            description=description,
        )
        await interaction.response.send_message(embed=JoyEmbed.success(f"Role {role.mention} ditambahkan ke panel #{panel_id} (entry `{entry_id}`)."))

    @reactionrole_group.command(name="removerole", description="Hapus satu entry role dari panel.")
    @_manage_roles_slash()
    async def rr_removerole_slash(self, interaction: discord.Interaction, entry_id: int):
        ok = await self.rr_service.remove_entry(entry_id)
        await interaction.response.send_message(embed=JoyEmbed.success("Entry dihapus.") if ok else JoyEmbed.error("Entry tidak ditemukan."))

    @reactionrole_group.command(name="post", description="Post panel ke channel.")
    @_manage_roles_slash()
    async def rr_post_slash(self, interaction: discord.Interaction, panel_id: int, channel: discord.TextChannel):
        panel = await self.rr_service.get_panel(panel_id, interaction.guild_id)
        if panel is None:
            await interaction.response.send_message(embed=JoyEmbed.error("Panel tidak ditemukan."), ephemeral=True)
            return
        entries = await self.rr_service.get_entries(panel_id)
        if not entries:
            await interaction.response.send_message(embed=JoyEmbed.error("Panel belum punya role."), ephemeral=True)
            return
        await self._post_panel(panel, channel)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Panel berhasil di-post di {channel.mention}."))

    @reactionrole_group.command(name="delete", description="Hapus panel reaction role.")
    @_manage_roles_slash()
    async def rr_delete_slash(self, interaction: discord.Interaction, panel_id: int):
        ok = await self.rr_service.delete_panel(panel_id, interaction.guild_id)
        await interaction.response.send_message(embed=JoyEmbed.success(f"Panel #{panel_id} dihapus.") if ok else JoyEmbed.error("Panel tidak ditemukan."))

    @reactionrole_group.command(name="list", description="Menampilkan daftar panel reaction role.")
    async def rr_list_slash(self, interaction: discord.Interaction):
        panels = await self.rr_service.list_panels(interaction.guild_id)
        if not panels:
            await interaction.response.send_message(embed=JoyEmbed.info("Belum ada panel reaction role."))
            return
        lines = [
            f"`#{p.id}` **{p.title}** — tipe `{p.panel_type}`"
            + (" • Unique" if p.unique_mode else "")
            + (" • Verification" if p.verification_mode else "")
            for p in panels
        ]
        await interaction.response.send_message(embed=JoyEmbed.info("\n".join(lines), title=f"{emoji.settings} Daftar Panel Reaction Role"))

    @reactionrole_group.command(name="info", description="Menampilkan detail panel reaction role.")
    async def rr_info_slash(self, interaction: discord.Interaction, panel_id: int):
        panel = await self.rr_service.get_panel(panel_id, interaction.guild_id)
        if panel is None:
            await interaction.response.send_message(embed=JoyEmbed.error("Panel tidak ditemukan."), ephemeral=True)
            return
        entries = await self.rr_service.get_entries(panel_id)
        lines = [f"`{e.id}` {e.emoji or ''} <@&{e.role_id}> — {e.label or '-'}" for e in entries]
        await interaction.response.send_message(embed=JoyEmbed.info(
            f"**Tipe:** {panel.panel_type}\n"
            f"**Unique Mode:** {'Ya' if panel.unique_mode else 'Tidak'}\n"
            f"**Verification Mode:** {'Ya' if panel.verification_mode else 'Tidak'}\n\n"
            f"**Entries:**\n" + ("\n".join(lines) if lines else "Belum ada role."),
            title=f"{emoji.info} Panel #{panel.id} — {panel.title}",
        ))


async def setup(bot: JoyUniverse):
    await bot.add_cog(Roles(bot))
