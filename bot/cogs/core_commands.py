"""
Cog Core Commands untuk JOY UNIVERSE.

Berisi command dasar yang harus ada di setiap bot profesional:
- help (dengan pagination button, jalan di prefix & slash)
- ping
- info / botinfo
"""

from __future__ import annotations

import time

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.bot import JoyUniverse
from bot.utils.embeds import JoyEmbed
from bot.utils.emojis import emoji


class HelpView(discord.ui.View):
    """Pagination sederhana untuk help command, satu embed per cog."""

    def __init__(self, pages: list[discord.Embed], author_id: int):
        super().__init__(timeout=90)
        self.pages = pages
        self.author_id = author_id
        self.index = 0
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.previous_button.disabled = self.index == 0
        self.next_button.disabled = self.index == len(self.pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                embed=JoyEmbed.error("Cuma yang memanggil command ini yang bisa geser halaman."),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Sebelumnya", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="Selanjutnya", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True  # type: ignore


class CoreCommands(commands.Cog):
    """Command dasar bot: help, ping, info."""

    def __init__(self, bot: JoyUniverse):
        self.bot = bot

    def _build_help_pages(self, invoker: discord.abc.User) -> list[discord.Embed]:
        pages: list[discord.Embed] = []

        overview = JoyEmbed.info(
            "Selamat datang di **JOY UNIVERSE** — bot serbaguna dengan moderasi, "
            "leveling, welcome/leave, event, dan masih terus berkembang.\n\n"
            f"Gunakan tombol di bawah untuk menjelajahi setiap kategori command.\n"
            f"Ketik `{self.bot.config.default_prefix}help <nama command>` untuk detail satu command "
            f"(termasuk daftar subcommand kalau itu group).",
            title=f"{emoji.info} JOY UNIVERSE — Help Menu",
        )
        overview.set_thumbnail(url=self.bot.user.display_avatar.url if self.bot.user else None)
        pages.append(overview)

        for cog_name, cog in sorted(self.bot.cogs.items()):
            cmds = [c for c in cog.get_commands() if not c.hidden]
            if not cmds:
                continue
            lines = []
            for c in sorted(cmds, key=lambda x: x.name):
                aliases = f" (`{'`, `'.join(c.aliases)}`)" if c.aliases else ""
                desc = c.short_doc or "Belum ada deskripsi."
                if isinstance(c, commands.Group) and c.commands:
                    desc += f" *(`{self.bot.config.default_prefix}help {c.name}` untuk {len(c.commands)} subcommand)*"
                lines.append(f"**`{c.name}`**{aliases} — {desc}")
            embed = JoyEmbed.info(
                "\n".join(lines),
                title=f"{emoji.settings} Kategori: {cog_name}",
            )
            pages.append(embed)

        return pages

    def _build_command_detail_embed(self, name: str) -> discord.Embed | None:
        name = name.strip().lstrip(self.bot.config.default_prefix).lstrip("/")
        command = self.bot.get_command(name)
        if command is None:
            return None

        embed = JoyEmbed.info(
            command.help or command.short_doc or "Belum ada deskripsi.",
            title=f"{emoji.info} Command: {command.qualified_name}",
        )
        if command.aliases:
            embed.add_field(name="Alias", value=", ".join(f"`{a}`" for a in command.aliases), inline=False)

        if isinstance(command, commands.Group) and command.commands:
            subs = sorted(command.commands, key=lambda c: c.name)
            lines = [f"**`{c.name}`** — {c.short_doc or 'Belum ada deskripsi.'}" for c in subs]
            embed.add_field(
                name=f"Subcommand ({len(subs)})",
                value="\n".join(lines),
                inline=False,
            )
        return embed

    @commands.command(name="help")
    async def help_prefix(self, ctx: commands.Context, *, command_name: str | None = None):
        """Menampilkan daftar command, atau detail satu command/group kalau diisi nama."""
        if command_name:
            embed = self._build_command_detail_embed(command_name)
            await ctx.send(embed=embed or JoyEmbed.error(f"Command `{command_name}` tidak ditemukan."))
            return

        pages = self._build_help_pages(ctx.author)
        view = HelpView(pages, ctx.author.id) if len(pages) > 1 else None
        await ctx.send(embed=pages[0], view=view)

    @app_commands.command(name="help", description="Menampilkan daftar command, atau detail satu command/group.")
    @app_commands.describe(command_name="Nama command/group untuk lihat detail (opsional)")
    async def help_slash(self, interaction: discord.Interaction, command_name: str | None = None):
        if command_name:
            embed = self._build_command_detail_embed(command_name)
            await interaction.response.send_message(embed=embed or JoyEmbed.error(f"Command `{command_name}` tidak ditemukan."))
            return

        pages = self._build_help_pages(interaction.user)
        view = HelpView(pages, interaction.user.id) if len(pages) > 1 else None
        await interaction.response.send_message(embed=pages[0], view=view)

    @commands.command(name="ping")
    async def ping_prefix(self, ctx: commands.Context):
        """Cek latency bot."""
        start = time.perf_counter()
        message = await ctx.send(embed=JoyEmbed.info("Mengecek latency..."))
        elapsed = (time.perf_counter() - start) * 1000
        embed = JoyEmbed.success(
            f"**Latency Bot:** `{elapsed:.0f}ms`\n**Latency WebSocket:** `{self.bot.latency * 1000:.0f}ms`",
            title=f"{emoji.success} Pong!",
        )
        await message.edit(embed=embed)

    @app_commands.command(name="ping", description="Cek latency bot.")
    async def ping_slash(self, interaction: discord.Interaction):
        embed = JoyEmbed.success(
            f"**Latency WebSocket:** `{self.bot.latency * 1000:.0f}ms`",
            title=f"{emoji.success} Pong!",
        )
        await interaction.response.send_message(embed=embed)

    @commands.command(name="info", aliases=["botinfo", "about"])
    async def info_prefix(self, ctx: commands.Context):
        """Menampilkan informasi tentang bot."""
        await ctx.send(embed=self._build_info_embed(ctx.guild))

    @app_commands.command(name="info", description="Menampilkan informasi tentang bot.")
    async def info_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=self._build_info_embed(interaction.guild))

    def _build_info_embed(self, guild: discord.Guild | None) -> discord.Embed:
        embed = JoyEmbed.info(
            "Bot serbaguna dengan tema kuning premium — moderasi, leveling, welcome/leave, "
            "dan event, dibangun untuk performa dan kestabilan jangka panjang.",
            title=f"{emoji.info} Tentang JOY UNIVERSE",
        )
        embed.add_field(name="Server", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Prefix Default", value=f"`{self.bot.config.default_prefix}`", inline=True)
        embed.add_field(name="Library", value="discord.py", inline=True)
        if self.bot.config.support_server:
            embed.add_field(name="Support Server", value=self.bot.config.support_server, inline=False)
        embed.set_default_footer(guild)
        return embed


async def setup(bot: JoyUniverse):
    await bot.add_cog(CoreCommands(bot))
