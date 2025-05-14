"""
Discord Loan Bot - A bot for managing loans in One Piece themed crews
"""

import discord
from discord.ext import commands, tasks
import os
import sys
import json
import asyncio
import datetime
import logging
import traceback

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("discord")

# Add current directory to system path to help with imports
sys.path.insert(0, os.getcwd())
logger.info(f"Python path: {sys.path}")

# Try to import config, use environment variables as fallback
try:
    import config
    logger.info("Config module imported successfully")
except ModuleNotFoundError:
    logger.warning("Config module not found, creating from environment variables")
    # Create a basic config module from environment variables
    import types
    config = types.ModuleType('config')
    config.DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
    config.CLIENT_ID = os.environ.get("CLIENT_ID", "")
    config.UNBELIEVABOAT = {
        "ENABLED": True,
        "API_KEY": os.environ.get("UNBELIEVABOAT_API_KEY", ""),
        "GUILD_ID": "",
        "CURRENCY_NAME": "Berries",
        "MANUAL_MODE": True,
        "BANK_ACCOUNT": "Bank",
        "COMMANDS": {
            "ADD": "!add",
            "PAY": "!pay",
            "BALANCE": "!balance"
        }
    }
    config.SERVER_SETTINGS = {}
    sys.modules['config'] = config
    logger.info("Created config module from environment variables")

# Try to import server_settings, create fallback if not found
try:
    import server_settings
    logger.info("Server settings module imported successfully")
except ModuleNotFoundError:
    logger.warning("Server settings module not found, creating fallback")
    # Create a basic server_settings module
    import types
    server_settings = types.ModuleType('server_settings')
    
    def load_settings():
        """Load server settings from file"""
        logger.info("Loading server settings (fallback implementation)")
        try:
            if os.path.exists("data/server_settings.json"):
                with open("data/server_settings.json", "r") as f:
                    settings = json.load(f)
                config.SERVER_SETTINGS = settings
                logger.info("Loaded server settings from file")
            else:
                logger.info("No server settings file found, using defaults")
        except Exception as e:
            logger.error(f"Error loading server settings: {e}")
    
    server_settings.load_settings = load_settings
    server_settings.save_settings = lambda: None
    server_settings.get_guild_settings = lambda guild_id: config.SERVER_SETTINGS.get(str(guild_id), {})
    server_settings.get_captain_role = lambda guild_id: server_settings.get_guild_settings(guild_id).get("captain_role_id", None)
    server_settings.check_is_captain = lambda guild_id, member: True  # Default allow everyone
    sys.modules['server_settings'] = server_settings
    logger.info("Created fallback server_settings module")

# Initialize bot with proper intents
intents = discord.Intents.all()  # Enable all intents for better functionality

# Create bot instance
bot = commands.Bot(command_prefix="/", intents=intents)

# Initialize database (in-memory)
bot.loan_database = {
    "loans": [],     # Array to store all active loans
    "history": [],   # Array to store loan history
    "credit_scores": {},  # Object to store credit scores by userId
    "loan_requests": []  # Array to store pending loan requests
}


@bot.event
async def on_ready():
    """Event triggered when the bot is ready"""
    logger.info(f"Logged in as {bot.user}")
    logger.info(f"Bot is in {len(bot.guilds)} servers")
    
    # List all guilds the bot is in
    for guild in bot.guilds:
        logger.info(f"Connected to guild: {guild.name} (ID: {guild.id})")
    
    # Start tasks
    backup_database.start()
    
    # No need to register commands on startup if they were already registered by deploy_commands.py
    # If you want to update commands, run deploy_commands.py manually
    
    logger.info("Bot is now online and ready to use! Type / to see available commands.")


@bot.event
async def on_interaction(interaction):
    """Event triggered when an interaction is received"""
    # The commands framework handles most interactions, but we can log them here
    if interaction.type == discord.InteractionType.application_command:
        logger.info(f"Command used: {interaction.command.name} by {interaction.user}")
    
    # Handle button interactions
    elif interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id", "")
        logger.info(f"Button clicked: {custom_id} by {interaction.user}")
        
        # Let the loan command cog handle loan approval/denial buttons
        if custom_id.startswith("approve_loan_") or custom_id.startswith("deny_loan_"):
            loan_command = bot.get_cog("LoanCommand")
            if loan_command:
                await loan_command.on_interaction(interaction)
            else:
                logger.error("LoanCommand cog not found for button interaction")


@tasks.loop(minutes=5)
async def backup_database():
    """Task to backup the database every 5 minutes"""
    try:
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Convert datetime objects to strings for JSON serialization
        database_copy = json.loads(json.dumps(bot.loan_database, default=str))
        
        # Save to file
        with open("data/database.json", "w") as f:
            json.dump(database_copy, f, indent=2)
            
        logger.info("Database backed up to file")
    except Exception as e:
        logger.error(f"Error saving database to backup: {e}")


async def load_commands():
    """Load all command cogs from the commands directory"""
    for filename in os.listdir("commands"):
        if filename.endswith(".py"):
            command_name = filename[:-3]  # Remove .py extension
            try:
                await bot.load_extension(f"commands.{command_name}")
                logger.info(f"Loaded command: {command_name}")
            except Exception as e:
                logger.error(f"Error loading command {command_name}: {e}")
                traceback.print_exc()


async def load_database():
    """Load database from backup file if available"""
    try:
        if os.path.exists("data/database.json"):
            with open("data/database.json", "r") as f:
                data = json.load(f)
                
                # Convert string dates back to datetime objects
                if "loans" in data:
                    for loan in data["loans"]:
                        if "request_date" in loan:
                            loan["request_date"] = datetime.datetime.fromisoformat(loan["request_date"])
                        if "due_date" in loan:
                            loan["due_date"] = datetime.datetime.fromisoformat(loan["due_date"])
                
                if "history" in data:
                    for loan in data["history"]:
                        if "request_date" in loan:
                            loan["request_date"] = datetime.datetime.fromisoformat(loan["request_date"])
                        if "due_date" in loan:
                            loan["due_date"] = datetime.datetime.fromisoformat(loan["due_date"])
                        if "repaid_date" in loan:
                            loan["repaid_date"] = datetime.datetime.fromisoformat(loan["repaid_date"])
                
                # Convert string dates in loan requests
                if "loan_requests" in data:
                    for request in data["loan_requests"]:
                        if "request_date" in request:
                            request["request_date"] = datetime.datetime.fromisoformat(request["request_date"])
                        if "due_date" in request:
                            request["due_date"] = datetime.datetime.fromisoformat(request["due_date"])
                        if "approved_date" in request:
                            request["approved_date"] = datetime.datetime.fromisoformat(request["approved_date"])
                        if "denied_date" in request:
                            request["denied_date"] = datetime.datetime.fromisoformat(request["denied_date"])
                
                # Update the bot's database
                if "loans" in data:
                    bot.loan_database["loans"] = data["loans"]
                if "history" in data:
                    bot.loan_database["history"] = data["history"]
                if "credit_scores" in data:
                    bot.loan_database["credit_scores"] = data["credit_scores"]
                if "loan_requests" in data:
                    bot.loan_database["loan_requests"] = data["loan_requests"]
                
                logger.info("Database loaded from backup file")
    except Exception as e:
        logger.error(f"Error loading database from backup: {e}")
        traceback.print_exc()


async def main():
    """Main function to start the bot"""
    try:
        # Load commands and database
        await load_commands()
        await load_database()
        
        # Load server settings
        server_settings.load_settings()
        
        # Try to connect to Discord
        logger.info("Attempting to connect to Discord with token...")
        
        # Check if token is valid
        if not config.DISCORD_TOKEN or len(config.DISCORD_TOKEN) < 50:
            logger.error(f"Invalid Discord token format. Token length: {len(config.DISCORD_TOKEN) if config.DISCORD_TOKEN else 0}")
            logger.error("Please check your DISCORD_TOKEN environment variable")
            return
        
        logger.info(f"Token starts with: {config.DISCORD_TOKEN[:10]}...")
        
        # Start the bot
        await bot.start(config.DISCORD_TOKEN)
    except discord.errors.LoginFailure as e:
        logger.error(f"Discord login failed: {e}")
        logger.error("This usually means your token is invalid. Please check your DISCORD_TOKEN environment variable.")
        logger.error(f"Token begins with: {config.DISCORD_TOKEN[:10]}..." if config.DISCORD_TOKEN else "Token is empty!")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        traceback.print_exc()


@bot.event
async def on_close():
    """Event triggered when the bot is closing"""
    logger.info("Bot is shutting down, cleaning up resources...")
    
    # Close the UnbelievaBoat API session if it exists
    try:
        for command_name in ["loan", "repay"]:
            command = bot.get_cog(f"{command_name.title()}Command")
            if command and hasattr(command, "unbelievaboat") and command.unbelievaboat:
                await command.unbelievaboat.close()
                logger.info(f"Closed UnbelievaBoat API session for {command_name} command")
    except Exception as e:
        logger.error(f"Error closing UnbelievaBoat API session: {e}")
    
    logger.info("Cleanup complete, bot shutting down.")


# Entry point
if __name__ == "__main__":
    # Run the bot
    asyncio.run(main()) 