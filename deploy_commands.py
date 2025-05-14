"""
Deploy slash commands to Discord

This script will deploy all slash commands to Discord.
Run this script when you add new commands or modify existing ones.
"""

import discord
from discord import app_commands
from discord.ext import commands
import config
import os
import sys
import asyncio
import logging


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("deploy")


async def deploy_commands():
    """Deploy slash commands to Discord"""
    # Initialize bot with proper intents
    intents = discord.Intents.default()
    
    # Create bot instance
    bot = commands.Bot(command_prefix="/", intents=intents)
    
    # Load all commands
    for filename in os.listdir("commands"):
        if filename.endswith(".py"):
            command_name = filename[:-3]  # Remove .py extension
            try:
                await bot.load_extension(f"commands.{command_name}")
                logger.info(f"Loaded command: {command_name}")
            except Exception as e:
                logger.error(f"Error loading command {command_name}: {e}")
                return
    
    # Login to Discord
    await bot.login(config.DISCORD_TOKEN)
    
    # Sync commands globally only
    logger.info("Syncing commands globally only...")
    await bot.tree.sync()
    logger.info("Commands synced successfully to all guilds!")
    
    logger.info("Command deployment completed. You can now start the bot.")


if __name__ == "__main__":
    asyncio.run(deploy_commands()) 