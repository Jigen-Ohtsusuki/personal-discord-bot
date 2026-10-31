import time
import platform
import discord
from discord import app_commands
from discord.ext import commands
from database import db

START_TIME = time.time()

class GeneralCog(commands.Cog, name="General & Gaming Essentials"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check bot latency and gateway responsiveness")
    async def ping(self, interaction: discord.Interaction):
        latency_ms = round(self.bot.latency * 1000, 1)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"**WebSocket Latency:** `{latency_ms} ms`\n**Status:** 🟢 Operational",
            color=0x2ECC71
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="botinfo", description="Display system statistics and bot information")
    async def botinfo(self, interaction: discord.Interaction):
        uptime_sec = int(time.time() - START_TIME)
        hours, remainder = divmod(uptime_sec, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"

        tracked_channels = await db.get_all_tracked_channel_ids()

        embed = discord.Embed(
            title="🎮 Jey's Bot 💜",
            description="Private Gaming Server Bot tailored for **MissJey (Jhanvi)** and her community.",
            color=0x9B59B6
        )
        embed.add_field(name="🌐 Guilds", value=f"`{len(self.bot.guilds)}`", inline=True)
        embed.add_field(name="👥 Total Members", value=f"`{sum(g.member_count for g in self.bot.guilds)}`", inline=True)
        embed.add_field(name="📺 Monitored YouTube Creators", value=f"`{len(tracked_channels)}`", inline=True)
        embed.add_field(name="⏱️ Uptime", value=f"`{uptime_str}`", inline=True)
        embed.add_field(name="🐍 Python", value=f"`{platform.python_version()}`", inline=True)
        embed.add_field(name="📦 discord.py", value=f"`{discord.__version__}`", inline=True)
        embed.set_footer(text="Designed for gaming servers & custom web dashboards")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="View commands and guide for configuring YouTube notifications")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 Gaming Bot Commands & Guide",
            description="Complete control over YouTube notifications with clear distinction between **Shorts, Live streams, Standard uploads, and Stream VODs**.",
            color=0x00E5FF
        )

        embed.add_field(
            name="📺 YouTube Notification Commands",
            value=(
                "• `/youtube add <creator> <channel> [role]` — Track a YouTube channel\n"
                "• `/youtube remove <creator>` — Stop tracking a channel\n"
                "• `/youtube list` — View all tracked channels & alert settings\n"
                "• `/youtube toggle <creator>` — Toggle Shorts, Live, VODs, or Videos on/off\n"
                "• `/youtube test <creator> <type>` — Preview how notification embeds look\n"
                "• `/youtube checknow` — Force an immediate check for new uploads"
            ),
            inline=False
        )

        embed.add_field(
            name="🎯 Content Differentiation",
            value=(
                "• 🔴 **Live Stream**: Instant alert when a creator goes live with red badge\n"
                "• 🩳 **YouTube Short**: Distinct vertical short badge & direct link\n"
                "• 🎬 **Uploaded Video**: Standard video release notification\n"
                "• 📼 **Stream VOD**: Replay notification when a past livestream finishes"
            ),
            inline=False
        )

        embed.add_field(
            name="🛠️ General Utility",
            value="• `/ping` — Check bot response time\n• `/botinfo` — Bot status & stats",
            inline=False
        )

        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCog(bot))
