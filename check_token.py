"""
Check if the Discord token is valid and display information about the bot
"""

import asyncio
import discord
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

logger = logging.getLogger("token_checker")

async def check_token():
    """Check if the token is valid and display information about the bot"""
    logger.info(f"Checking token: {config.DISCORD_TOKEN[:12]}...")
    
    # Create a simple client with no intents
    client = discord.Client(intents=discord.Intents.default())
    
    @client.event
    async def on_ready():
        logger.info(f"Successfully logged in as: {client.user} (ID: {client.user.id})")
        logger.info(f"Bot is in {len(client.guilds)} servers")
        
        if len(client.guilds) > 0:
            logger.info("Servers the bot is in:")
            for guild in client.guilds:
                logger.info(f"- {guild.name} (ID: {guild.id})")
        else:
            logger.info("The bot is not in any servers!")
            logger.info("Invite link: " + create_invite_link(client.user.id))
        
        await client.close()
    
    try:
        await client.start(config.DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("❌ Invalid token! Please check your token in config.py")
        logger.info("You can generate a new token at: https://discord.com/developers/applications")
    except Exception as e:
        logger.error(f"Error connecting to Discord: {e}")

def create_invite_link(client_id):
    """Create an invite link for the bot"""
    permissions = discord.Permissions(
        send_messages=True,
        read_messages=True,
        embed_links=True,
        attach_files=True,
        read_message_history=True,
        use_slash_commands=True,
        manage_messages=True
    )
    
    return discord.utils.oauth_url(
        client_id, 
        permissions=permissions, 
        scopes=("bot", "applications.commands")
    )

# Run the function
asyncio.run(check_token()) 