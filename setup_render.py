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

if __name__ == "__main__":
    print("Running setup for Render deployment...")
    ensure_directories()
    
    if check_environment_variables():
        print("Environment variables are properly set")
    else:
        print("Missing environment variables! Bot may not function correctly.")
    
    print("Setup complete. Running the main bot...")
    
    # Run the main bot script
    try:
        subprocess.run([sys.executable, "run_bot.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running the bot: {e}")
        sys.exit(1) 