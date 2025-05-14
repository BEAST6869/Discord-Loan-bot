"""
Script to completely remove all Discord commands
"""

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import config
import logging


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("cleanup")


async def delete_all_commands():
    """Delete all application commands, both global and guild-specific"""
    try:
        logger.info("Started deleting all application commands...")
        
        # Create a simple client
        intents = discord.Intents.default()
        client = discord.Client(intents=intents)
        
        # Just log in without connecting to gateway
        await client.login(config.DISCORD_TOKEN)
        
        # Set up the application_id
        application_id = config.CLIENT_ID
        
        # Delete global commands
        logger.info("Deleting global application commands...")
        await client.http.bulk_upsert_global_commands(application_id, [])
        logger.info("Successfully deleted all global application commands.")
        
        # Try to delete commands from known guild
        guild_id = "1294261720440635434"  # From previous config
        logger.info(f"Deleting guild commands for guild ID: {guild_id}...")
        try:
            await client.http.bulk_upsert_guild_commands(application_id, guild_id, [])
            logger.info(f"Successfully deleted commands for guild {guild_id}.")
        except Exception as e:
            logger.error(f"Error deleting commands for guild {guild_id}: {e}")
            
        # Also try any other guilds from logs
        other_guilds = ["1351637782161784895"]  # From bot log output
        for guild_id in other_guilds:
            try:
                logger.info(f"Deleting guild commands for guild ID: {guild_id}...")
                await client.http.bulk_upsert_guild_commands(application_id, guild_id, [])
                logger.info(f"Successfully deleted commands for guild {guild_id}.")
            except Exception as e:
                logger.error(f"Error deleting commands for guild {guild_id}: {e}")
        
        logger.info("Command cleanup completed. Now run deploy_commands.py to register only the global commands.")
        
        # Close the HTTP session
        await client.http.close()
        
    except Exception as error:
        logger.error(f"Error deleting commands: {error}")


if __name__ == "__main__":
    # Execute the function
    asyncio.run(delete_all_commands()) 