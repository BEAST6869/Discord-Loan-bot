"""
Test the installment commands separately to diagnose issues
"""

import discord
from discord.ext import commands
import logging
import asyncio
import config
import os

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Use DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("test_installment")

async def main():
    # Initialize bot with proper intents
    intents = discord.Intents.default()
    
    # Create bot instance
    bot = commands.Bot(command_prefix="/", intents=intents)
    
    # Try to load just the installment command
    try:
        await bot.load_extension("commands.installment")
        logger.info("Successfully loaded installment module")
    except Exception as e:
        logger.error(f"Error loading installment module: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return
    
    # Login to Discord (but don't connect to the gateway)
    await bot.login(config.DISCORD_TOKEN)
    
    # Sync commands for this specific command
    logger.info("Syncing commands globally...")
    
    try:
        await bot.tree.sync()
        logger.info("Commands synced successfully!")
    except Exception as e:
        logger.error(f"Error syncing commands: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return
        
    logger.info("Command registration completed. Check Discord to see if the commands are available.")
    
    # Clean up
    await bot.close()

if __name__ == "__main__":
    asyncio.run(main()) 