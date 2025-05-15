"""
Deploy slash commands to Discord

This script will deploy all slash commands to Discord.
Run this script when you add new commands or modify existing ones.
"""

import discord
from discord.ext import commands
import asyncio
import sys
import logging
import config
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('discord')

# List all command cogs to load
COMMAND_EXTENSIONS = [
    "commands.help",
    "commands.loan",
    "commands.repay",
    "commands.setup",
    "commands.loan_setup"
]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    logger.info(f'Bot is in {len(bot.guilds)} servers')
    
    try:
        # Load all command extensions
        for extension in COMMAND_EXTENSIONS:
            try:
                await bot.load_extension(extension)
                logger.info(f"Loaded extension: {extension}")
            except Exception as e:
                logger.error(f"Failed to load extension {extension}: {e}")
        
        # Sync commands globally
        await bot.tree.sync()
        logger.info("Synced commands globally")
        
        # Sync commands to each guild for guild-specific commands
        for guild in bot.guilds:
            try:
                await bot.tree.sync(guild=guild)
                logger.info(f"Synced commands to guild: {guild.name} (ID: {guild.id})")
            except Exception as e:
                logger.error(f"Error syncing commands to guild {guild.name}: {e}")
        
        logger.info("All commands have been deployed successfully!")
    except Exception as e:
        logger.error(f"Error deploying commands: {e}")
    finally:
        # Exit the bot
        await bot.close()

if __name__ == "__main__":
    token = config.DISCORD_TOKEN
    if not token:
        logger.error("No token found in config.py")
        sys.exit(1)
        
    bot.run(token) 