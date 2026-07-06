"""
Cog Owner Mode untuk JOY UNIVERSE.

Berisi command yang hanya boleh dipakai Owner/Bot Admin:
- Maintenance Mode (on/off + reason + embed otomatis)
- Reload Cog
- Sync Slash Command
- Emergency Shutdown
- Kelola No-Prefix user & Bot Admin
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.bot import JoyUniverse
from bot.utils.embeds import JoyEmbed
from bot.utils.emojis import emoji, EmojiManager

logger = logging.getLogger("joyuniverse.cogs.owner")


def is_bot_admin():
    async def predicate(ctx: commands.Context) -> bool:
        bot: JoyUniverse = ctx.bot  # type: ignore
        if not bot.is_bot_admin(ctx.author.id):
            raise commands.CheckFailure("Hanya Bot Owner/Admin yang boleh memakai command ini.")
        return True

    return commands.check(predicate)


class Owner(commands.Cog):
    """Owner-only tools: maintenance, reload, sync, shutdown."""

    def __init__(self, bot: JoyUniverse):
        self.bot = bot

    # ---------- Maintenance Mode ----------

    @commands.command(name="maintenance", aliases=["maint"])
    @is_bot_admin()
    async def maintenance(self, ctx: commands.Context, state: str, *, reason: str | None = None):
        """Aktifkan/nonaktifkan maintenance mode. Contoh: !maintenance on Perbaikan database"""
        state = state.lower()
        if state not in ("on", "off"):
            await ctx.send(embed=JoyEmbed.error("Gunakan `on` atau `off`. Contoh: `!maintenance on Perbaikan database`"))
            return

        is_active = state == "on"
        await self.bot.db.execute(
            """
            UPDATE maintenance_state
            SET is_active = ?, reason = ?, activated_by = ?, activated_at = datetime('now')
            WHERE id = 1
            """,
            (int(is_active), reason, str(ctx.author.id)),
        )
        await self.bot.refresh_maintenance_state()

        if is_active:
            embed = JoyEmbed.warning(
                reason or "Bot sedang dalam perbaikan, mohon tunggu sebentar.",
                title=f"{emoji.maintenance} Maintenance Mode Aktif",
            )
        else:
            embed = JoyEmbed.success("Maintenance mode dinonaktifkan. Bot kembali normal.")

        await ctx.send(embed=embed)

    # ---------- Reload Cog ----------

    @commands.command(name="reload")
    @is_bot_admin()
    async def reload(self, ctx: commands.Context, extension: str = "all"):
        """Reload satu cog atau semua cog. Contoh: !reload owner / !reload all"""
        EmojiManager.reload()

        if extension == "all":
            reloaded, failed = [], []
            for ext_name in list(self.bot.extensions.keys()):
                try:
                    await self.bot.reload_extension(ext_name)
                    reloaded.append(ext_name)
                except Exception as e:
                    failed.append(f"{ext_name}: {e}")

            desc = f"Berhasil reload **{len(reloaded)}** cog."
            if failed:
                desc += "\n\nGagal:\n" + "\n".join(f"`{f}`" for f in failed)
            await ctx.send(embed=JoyEmbed.success(desc) if not failed else JoyEmbed.warning(desc))
            return

        target = extension if extension.startswith("bot.cogs.") else f"bot.cogs.{extension}"
        try:
            await self.bot.reload_extension(target)
            await ctx.send(embed=JoyEmbed.success(f"Cog `{target}` berhasil di-reload."))
        except Exception as e:
            await ctx.send(embed=JoyEmbed.error(f"Gagal reload `{target}`:\n```{e}```"))

    # ---------- Sync Slash Command ----------

    @commands.command(name="sync")
    @is_bot_admin()
    async def sync(self, ctx: commands.Context, scope: str = "guild"):
        """Sync slash command. `!sync guild` (cepat, khusus server ini) atau `!sync global`."""
        async with ctx.typing():
            if scope == "global":
                synced = await self.bot.tree.sync()
                await ctx.send(embed=JoyEmbed.success(f"{len(synced)} slash command di-sync secara global."))
            else:
                if ctx.guild is None:
                    await ctx.send(embed=JoyEmbed.error("Command ini harus dipakai di dalam server untuk sync guild."))
                    return
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
                await ctx.send(embed=JoyEmbed.success(f"{len(synced)} slash command di-sync untuk server ini."))

    # ---------- Emergency Shutdown ----------

    @commands.command(name="shutdown", aliases=["stop"])
    @is_bot_admin()
    async def shutdown(self, ctx: commands.Context):
        """Mematikan bot secara aman (Railway akan menandainya sebagai stopped, bukan crash)."""
        await ctx.send(embed=JoyEmbed.warning("Mematikan bot sekarang..."))
        logger.warning("Shutdown dipicu oleh %s (%s)", ctx.author, ctx.author.id)
        await self.bot.close()

    # ---------- No-Prefix management ----------

    @commands.group(name="noprefix", invoke_without_command=True)
    @is_bot_admin()
    async def noprefix(self, ctx: commands.Context):
        await ctx.send(embed=JoyEmbed.info("Gunakan `!noprefix add @user` atau `!noprefix remove @user`."))

    @noprefix.command(name="add")
    @is_bot_admin()
    async def noprefix_add(self, ctx: commands.Context, user: discord.User):
        await self.bot.db.execute(
            "INSERT OR IGNORE INTO no_prefix_users (user_id, added_by) VALUES (?, ?)",
            (str(user.id), str(ctx.author.id)),
        )
        await self.bot.refresh_no_prefix_cache()
        await ctx.send(embed=JoyEmbed.success(f"{user.mention} sekarang bisa memakai command tanpa prefix."))

    @noprefix.command(name="remove")
    @is_bot_admin()
    async def noprefix_remove(self, ctx: commands.Context, user: discord.User):
        await self.bot.db.execute("DELETE FROM no_prefix_users WHERE user_id = ?", (str(user.id),))
        await self.bot.refresh_no_prefix_cache()
        await ctx.send(embed=JoyEmbed.success(f"Akses no-prefix {user.mention} dicabut."))

    # ---------- Bot Admin management (owner asli saja) ----------

    @commands.command(name="addadmin")
    @commands.is_owner()
    async def add_admin(self, ctx: commands.Context, user: discord.User):
        await self.bot.db.execute(
            "INSERT OR IGNORE INTO bot_admins (user_id, added_by) VALUES (?, ?)",
            (str(user.id), str(ctx.author.id)),
        )
        await self.bot.refresh_bot_admin_cache()
        await ctx.send(embed=JoyEmbed.success(f"{user.mention} sekarang menjadi Bot Admin."))

    @commands.command(name="removeadmin")
    @commands.is_owner()
    async def remove_admin(self, ctx: commands.Context, user: discord.User):
        await self.bot.db.execute("DELETE FROM bot_admins WHERE user_id = ?", (str(user.id),))
        await self.bot.refresh_bot_admin_cache()
        await ctx.send(embed=JoyEmbed.success(f"{user.mention} tidak lagi menjadi Bot Admin."))

    async def cog_check(self, ctx: commands.Context) -> bool:
        # Fallback: commands.is_owner() dari discord.py cuma cek application owner,
        # jadi kita override supaya Bot Admin dari DB juga otomatis lolos default check.
        return True


async def setup(bot: JoyUniverse):
    await bot.add_cog(Owner(bot))
