"""
Error handler terpusat untuk prefix command & slash command JOY UNIVERSE.
Semua pesan error dikirim dalam bahasa Indonesia dengan embed konsisten.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.utils.embeds import JoyEmbed

logger = logging.getLogger("joyuniverse.errors")


async def handle_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    error = getattr(error, "original", error)

    if isinstance(error, commands.CommandNotFound):
        return  # diabaikan supaya no-prefix mode tidak spam error di chat biasa

    if isinstance(error, commands.CommandOnCooldown):
        embed = JoyEmbed.warning(
            f"Tunggu **{error.retry_after:.1f} detik** lagi sebelum memakai command ini."
        )
    elif isinstance(error, commands.MissingPermissions):
        perms = ", ".join(error.missing_permissions)
        embed = JoyEmbed.error(f"Kamu butuh permission berikut: `{perms}`")
    elif isinstance(error, commands.BotMissingPermissions):
        perms = ", ".join(error.missing_permissions)
        embed = JoyEmbed.error(f"Bot butuh permission berikut: `{perms}`")
    elif isinstance(error, commands.NoPrivateMessage):
        embed = JoyEmbed.error("Command ini hanya bisa dipakai di dalam server.")
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = JoyEmbed.error(f"Argumen `{error.param.name}` wajib diisi.")
    elif isinstance(error, commands.BadArgument):
        embed = JoyEmbed.error("Argumen yang kamu masukkan tidak valid.")
    elif isinstance(error, commands.CheckFailure):
        embed = JoyEmbed.error("Kamu tidak punya akses untuk memakai command ini.")
    else:
        logger.exception("Unhandled command error di '%s'", ctx.command, exc_info=error)
        embed = JoyEmbed.error(
            "Terjadi kesalahan tak terduga. Tim developer sudah otomatis dicatat."
        )

    try:
        await ctx.send(embed=embed)
    except discord.HTTPException:
        pass


async def handle_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    error = getattr(error, "original", error)

    if isinstance(error, app_commands.CommandOnCooldown):
        embed = JoyEmbed.warning(
            f"Tunggu **{error.retry_after:.1f} detik** lagi sebelum memakai command ini."
        )
    elif isinstance(error, app_commands.MissingPermissions):
        perms = ", ".join(error.missing_permissions)
        embed = JoyEmbed.error(f"Kamu butuh permission berikut: `{perms}`")
    elif isinstance(error, app_commands.BotMissingPermissions):
        perms = ", ".join(error.missing_permissions)
        embed = JoyEmbed.error(f"Bot butuh permission berikut: `{perms}`")
    elif isinstance(error, app_commands.NoPrivateMessage):
        embed = JoyEmbed.error("Command ini hanya bisa dipakai di dalam server.")
    elif isinstance(error, app_commands.CheckFailure):
        embed = JoyEmbed.error("Kamu tidak punya akses untuk memakai command ini.")
    else:
        logger.exception("Unhandled app command error", exc_info=error)
        embed = JoyEmbed.error(
            "Terjadi kesalahan tak terduga. Tim developer sudah otomatis dicatat."
        )

    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except discord.HTTPException:
        pass
