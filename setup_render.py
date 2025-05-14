"""
Setup script to ensure required directories exist for Render hosting
"""

import os
import sys
import subprocess
import importlib
import time

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
    print(f"Current working directory: {os.getcwd()}")
    
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
    
    # Verify the file was created
    if os.path.exists("config.py"):
        print(f"config.py has been generated successfully at {os.path.abspath('config.py')}")
        # List all files in current directory for debugging
        print("Files in current directory:")
        for file in os.listdir():
            print(f"  - {file}")
    else:
        print("ERROR: Failed to create config.py file!")

def verify_config_module():
    """Verify that the config module can be imported"""
    print("Verifying config module can be imported...")
    try:
        # Make sure module can be found
        sys.path.insert(0, os.getcwd())
        print(f"Python path: {sys.path}")
        
        # Attempt to import
        print("Attempting to import config module...")
        import config
        print("Config module imported successfully!")
        print(f"DISCORD_TOKEN starts with: {config.DISCORD_TOKEN[:5]}...")
        return True
    except Exception as e:
        print(f"ERROR importing config module: {e}")
        return False

def run_bot_direct():
    """Run the bot directly instead of through the watchdog"""
    print("Running bot directly due to config issues...")
    try:
        # Create a simple bot runner that doesn't require config import
        direct_runner = """
import sys
import os

# Make sure current directory is in path
sys.path.insert(0, os.getcwd())

# Import the bot main module
import bot
import asyncio

# Run the bot
asyncio.run(bot.main())
"""
        with open("direct_runner.py", "w") as f:
            f.write(direct_runner)
        
        # Run the direct runner
        subprocess.run([sys.executable, "direct_runner.py"], check=True)
    except Exception as e:
        print(f"ERROR running bot directly: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Running setup for Render deployment...")
    print(f"Python version: {sys.version}")
    ensure_directories()
    
    if check_environment_variables():
        print("Environment variables are properly set")
    else:
        print("WARNING: Missing environment variables! Bot may not function correctly.")
    
    # Generate config.py from environment variables
    generate_config_file()
    
    # Verify config module can be imported
    if not verify_config_module():
        print("WARNING: Config module could not be imported. Trying alternative approach.")
        run_bot_direct()
        sys.exit(1)
    
    print("Setup complete. Running the main bot...")
    
    # Run the main bot script
    try:
        subprocess.run([sys.executable, "run_bot.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running the bot: {e}")
        sys.exit(1) 