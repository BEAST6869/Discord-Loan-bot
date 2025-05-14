"""Discord bot configuration"""
import os

# Get token from environment variable for Render hosting or use default for local development
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "YOUR_DISCORD_TOKEN")

# Your client ID
CLIENT_ID = os.environ.get("CLIENT_ID", "YOUR_CLIENT_ID")

# UnbelievaBoat integration
UNBELIEVABOAT = {
    "ENABLED": True,  # Enable API integration
    "API_KEY": os.environ.get("UNBELIEVABOAT_API_KEY", "YOUR_UNBELIEVABOAT_API_KEY"),  # Your UnbelievaBoat JWT API token
    "GUILD_ID": "",  # Empty string to allow bot to work in any guild
    "CURRENCY_NAME": "Berries",  # The name of your currency
    
    # Manual mode is now always enabled as a fallback
    "MANUAL_MODE": True,  # Keep manual mode enabled as a fallback
    "BANK_ACCOUNT": "Bank",
    "COMMANDS": {
        "ADD": "!add",
        "PAY": "!pay",
        "BALANCE": "!balance"
    }
}

# Server-specific settings
# This will be dynamically populated and saved to a file
SERVER_SETTINGS = {
    # Format:
    # "guild_id": {
    #     "captain_role_id": "role_id"  # Role ID that can take loans
    # }
} 