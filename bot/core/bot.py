"""
Custom Bot class untuk JOY UNIVERSE.

Menangani:
- Prefix Command (per-guild, tersimpan di database)
- Mention Command (@JOY UNIVERSE help)
- No-Prefix Command (khusus owner & user yang diizinkan lewat DB)
- Slash Command (via app_commands, sync manual lewat command owner)
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from bot.core.config import config
from bot.database.connection import Database
from bot.services.guild_config_service import GuildConfigService

logger = logging.getLogger("joyuniverse.bot")


class JoyUniverse(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix=self._resolve_prefix,
            intents=intents,
            help_command=None,  # help command custom, dibuat di cogs/core_commands.py
            case_insensitive=True,
        )

        self.config = config
        self.db = Database(config.database_url)
        self.guild_configs: GuildConfigService | None = None

        # Cache ringan di memori supaya no-prefix check tidak selalu hit DB
        self._no_prefix_users: set[int] = set()
        self._bot_admins: set[int] = set()
        self.maintenance_mode: bool = False
        self.maintenance_reason: str | None = None

    # ---------- Prefix resolver ----------

    async def _resolve_prefix(self, bot: "JoyUniverse", message: discord.Message):
        """
        Mengembalikan daftar prefix yang valid untuk message ini:
        - Mention bot (@JOY UNIVERSE)
        - Prefix custom per-guild dari database
        - String kosong "" HANYA jika user termasuk no-prefix user (owner/allowed)
          -> ini yang bikin `@JOY UNIVERSE help` atau bahkan tanpa prefix bisa jalan
        """
        prefixes: list[str] = []

        if message.guild is not None and self.guild_configs is not None:
            guild_cfg = await self.guild_configs.get(message.guild.id)
            prefixes.append(guild_cfg.prefix)
        else:
            prefixes.append(self.config.default_prefix)

        # No-Prefix: hanya untuk owner & user yang di-whitelist
        if message.author.id in self._no_prefix_users or message.author.id == self.config.owner_id:
            prefixes.append("")

        return commands.when_mentioned_or(*prefixes)(bot, message)

    # ---------- Owner / admin helpers ----------

    def is_bot_owner(self, user_id: int) -> bool:
        return user_id == self.config.owner_id

    def is_bot_admin(self, user_id: int) -> bool:
        return self.is_bot_owner(user_id) or user_id in self._bot_admins

    async def refresh_no_prefix_cache(self) -> None:
        rows = await self.db.fetchall("SELECT user_id FROM no_prefix_users")
        self._no_prefix_users = {int(row["user_id"]) for row in rows}

    async def refresh_bot_admin_cache(self) -> None:
        rows = await self.db.fetchall("SELECT user_id FROM bot_admins")
        self._bot_admins = {int(row["user_id"]) for row in rows}

    async def refresh_maintenance_state(self) -> None:
        row = await self.db.fetchone(
            "SELECT is_active, reason FROM maintenance_state WHERE id = 1"
        )
        if row is not None:
            self.maintenance_mode = bool(row["is_active"])
            self.maintenance_reason = row["reason"]

    # ---------- Lifecycle ----------

    async def setup_hook(self) -> None:
        await self.db.connect()
        await self.db.run_migrations("bot/database/migrations")

        self.guild_configs = GuildConfigService(self.db)

        await self.refresh_no_prefix_cache()
        await self.refresh_bot_admin_cache()
        await self.refresh_maintenance_state()

        for extension in (
            "bot.cogs.owner",
            "bot.cogs.core_commands",
            "bot.cogs.welcome",
            "bot.cogs.leave",
            "bot.cogs.events",
            "bot.cogs.leveling",
        ):
            try:
                await self.load_extension(extension)
                logger.info("Cog dimuat: %s", extension)
            except Exception:
                logger.exception("Gagal memuat cog: %s", extension)

        logger.info("setup_hook selesai.")

    async def on_ready(self) -> None:
        logger.info("Login sebagai %s (ID: %s)", self.user, self.user.id if self.user else "?")
        logger.info("Terhubung ke %d server.", len(self.guilds))
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{self.config.default_prefix}help | JOY UNIVERSE",
            )
        )

    async def close(self) -> None:
        await self.db.close()
        await super().close()
