import asyncio
import logging
import sys
import discord
from discord.ext import commands

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import config
from database import db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DiscordBot")

# Define Bot Intents
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.reactions = True
intents.members = True

class GamingBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        # 1. Initialize SQLite Database
        logger.info("Initializing database...")
        await db.init_db()
        logger.info("Database schema initialized.")

        # 2. Load Cogs
        initial_extensions = [
            "cogs.youtube",
            "cogs.color_roles",
            "cogs.game_roles"
        ]

        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                logger.info(f"Loaded extension: {extension}")
            except Exception as e:
                logger.error(f"Failed to load extension {extension}: {e}", exc_info=True)

        # 3. Clear Slash Commands (100% automated background mode - zero commands needed)
        try:
            self.tree.clear_commands(guild=None)
            if config.GUILD_ID:
                guild_obj = discord.Object(id=int(config.GUILD_ID))
                self.tree.clear_commands(guild=guild_obj)
                await self.tree.sync(guild=guild_obj)
            await self.tree.sync()
            logger.info("Cleared slash commands. Running in zero-command automated mode.")
        except Exception as e:
            logger.debug(f"Command tree sync: {e}")

    async def on_ready(self):
        logger.info(f"=======================================")
        logger.info(f" Bot Logged In: {self.user.name} ({self.user.id})")
        logger.info(f" Connected Guilds: {len(self.guilds)}")
        logger.info(f" Server Mode: Dedicated to MissJey's Community")
        logger.info(f"=======================================")

        # Rich Presence Activity
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="MissJey Gaming 💜 | /help"
        )
        await self.change_presence(status=discord.Status.online, activity=activity)

async def main():
    if not config.DISCORD_TOKEN or config.DISCORD_TOKEN == "your_discord_bot_token_here":
        sep = "=" * 60
        logger.warning(f"\n{sep}\n [!] DISCORD_TOKEN is missing or not set in .env file!\n Please create a .env file and paste your bot token:\n DISCORD_TOKEN=your_token_here\n{sep}")
        print("Please configure .env before starting the bot.")
        return

    bot = GamingBot()
    async with bot:
        await bot.start(config.DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot process interrupted by user. Shutting down gracefully.")
