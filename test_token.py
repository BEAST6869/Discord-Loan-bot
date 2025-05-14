"""
Test script to verify Discord token validity
"""

import os
import sys
import asyncio
import discord

async def test_token():
    """Test if the Discord token is valid"""
    token = os.environ.get("DISCORD_TOKEN", "")
    
    if not token:
        print("ERROR: No Discord token found in environment variables")
        return False
    
    print(f"Token length: {len(token)}")
    print(f"Token starts with: {token[:10]}...")
    
    try:
        # Create a simple client
        intents = discord.Intents.default()
        client = discord.Client(intents=intents)
        
        # Define event handler
        @client.event
        async def on_ready():
            print(f"Successfully logged in as {client.user}")
            await client.close()
        
        # Try to login
        print("Attempting to connect to Discord...")
        await client.start(token)
        return True
    
    except discord.errors.LoginFailure as e:
        print(f"ERROR: Failed to login to Discord: {e}")
        print("This usually means your token is invalid or has been revoked.")
        return False
    
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("Testing Discord token validity...")
    
    # Print all environment variables (censored) for debugging
    print("\nEnvironment Variables:")
    for key, value in os.environ.items():
        if key == "DISCORD_TOKEN" and value:
            print(f"{key}={value[:10]}...{value[-4:]}")
        elif "TOKEN" in key.upper() or "KEY" in key.upper() or "SECRET" in key.upper():
            print(f"{key}={'*' * min(10, len(value)) if value else 'empty'}")
        else:
            print(f"{key}={value[:5]}..." if value and len(value) > 5 else f"{key}={value}")
    
    result = asyncio.run(test_token())
    
    if result:
        print("\nToken is VALID! ✅")
        sys.exit(0)
    else:
        print("\nToken is INVALID! ❌")
        sys.exit(1) 