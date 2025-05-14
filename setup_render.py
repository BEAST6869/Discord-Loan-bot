"""
Setup script to ensure required directories exist for Render hosting
"""

import os
import sys
import subprocess

def ensure_directories():
    """Ensure all required directories exist"""
    required_dirs = [
        "data",
        "commands",
        "logs"
    ]
    
    for directory in required_dirs:
        if not os.path.exists(directory):
            print(f"Creating directory: {directory}")
            os.makedirs(directory, exist_ok=True)

def check_environment_variables():
    """Check that required environment variables are set"""
    required_vars = [
        "DISCORD_TOKEN",
        "CLIENT_ID"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"WARNING: Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    return True

def generate_config_file():
    """Generate config.py file from environment variables"""
    print("Generating config.py from environment variables...")
    
    config_content = """\"\"\"Discord bot configuration\"\"\"
import os

# Discord token
DISCORD_TOKEN = "{}"

# Your client ID
CLIENT_ID = "{}"

# UnbelievaBoat integration
UNBELIEVABOAT = {{
    "ENABLED": True,  # Enable API integration
    "API_KEY": "{}",  # Your UnbelievaBoat JWT API token
    "GUILD_ID": "",  # Empty string to allow bot to work in any guild
    "CURRENCY_NAME": "Berries",  # The name of your currency
    
    # Manual mode is now always enabled as a fallback
    "MANUAL_MODE": True,  # Keep manual mode enabled as a fallback
    "BANK_ACCOUNT": "Bank",
    "COMMANDS": {{
        "ADD": "!add",
        "PAY": "!pay",
        "BALANCE": "!balance"
    }}
}}

# Server-specific settings
# This will be dynamically populated and saved to a file
SERVER_SETTINGS = {{
    # Format:
    # "guild_id": {{
    #     "captain_role_id": "role_id"  # Role ID that can take loans
    # }}
}}
""".format(
        os.environ.get("DISCORD_TOKEN", ""),
        os.environ.get("CLIENT_ID", ""),
        os.environ.get("UNBELIEVABOAT_API_KEY", "")
    )
    
    with open("config.py", "w") as f:
        f.write(config_content)
    
    print("config.py has been generated")

if __name__ == "__main__":
    print("Running setup for Render deployment...")
    ensure_directories()
    
    if check_environment_variables():
        print("Environment variables are properly set")
    else:
        print("Missing environment variables! Bot may not function correctly.")
    
    # Generate config.py from environment variables
    generate_config_file()
    
    print("Setup complete. Running the main bot...")
    
    # Run the main bot script
    try:
        subprocess.run([sys.executable, "run_bot.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running the bot: {e}")
        sys.exit(1) 