"""
Script to completely remove all Discord commands
"""

import discord
from discord.ext import commands
import asyncio
import os
import sys
import logging
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('discord')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    logger.info('Bot is now online and ready to clean up commands!')
    
    try:
        # Clear global commands
        await bot.tree.sync()
        logger.info("Cleared global commands")
        
        # Clear commands for each guild
        for guild in bot.guilds:
            logger.info(f"Clearing commands for guild: {guild.name} (ID: {guild.id})")
            
            # Get existing commands
            existing_commands = await bot.tree.fetch_commands(guild=guild)
            logger.info(f"Found {len(existing_commands)} commands in {guild.name}")
            
            # Delete all commands in this guild
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)
            
            logger.info(f"Successfully cleared commands for {guild.name}")
            
        logger.info("All commands have been removed successfully!")
    except Exception as e:
        logger.error(f"Error clearing commands: {e}")
    finally:
        # Exit the bot
        await bot.close()

if __name__ == "__main__":
    token = config.DISCORD_TOKEN
    if not token:
        logger.error("No token found in config.py")
        sys.exit(1)
        
    bot.run(token) 