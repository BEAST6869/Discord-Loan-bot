"""
Check if the UnbelievaBoat API token is valid and working
"""

import asyncio
import config
import logging
import json
import os
from unbelievaboat_integration import UnbelievaBoatAPI

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("unbelievaboat_checker")

async def check_api():
    """Check if the UnbelievaBoat API token is valid and working"""
    logger.info(f"Checking UnbelievaBoat API token: {config.UNBELIEVABOAT['API_KEY'][:12]}...")
    
    # Try to get port configuration from environment
    unbelievaboat_port = None
    try:
        port_env = os.environ.get('UNBELIEVABOAT_PORT')
        if port_env:
            unbelievaboat_port = int(port_env)
            logger.info(f"Using UnbelievaBoat port from environment: {unbelievaboat_port}")
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid UNBELIEVABOAT_PORT environment variable: {e}")
    
    # Create API client with appropriate configuration
    api = UnbelievaBoatAPI(
        api_key=config.UNBELIEVABOAT["API_KEY"],
        port=unbelievaboat_port,
        timeout=45  # Increased timeout for potential network delays
    )
    
    # Check if token works - we need a guild and user ID to test with
    guild_id = input("Enter a guild ID to test with: ")
    user_id = input("Enter your user ID to test with: ")
    
    logger.info(f"Testing with guild ID: {guild_id}, user ID: {user_id}")
    
    try:
        # Try to get user balance
        logger.info("Testing get_user_balance...")
        balance = await api.get_user_balance(guild_id, user_id)
        
        if balance:
            logger.info(f"✅ API token is valid! Got balance: {json.dumps(balance, indent=2)}")
        else:
            logger.error("❌ Could not get user balance. The API token might be invalid or the user/guild IDs are incorrect.")
            logger.info("Try enabling UnbelievaBoat bot in your server and ensure it has permissions.")
        
        # Clean up
        await api.close()
        
    except Exception as e:
        logger.error(f"Error testing API: {e}")
        await api.close()

if __name__ == "__main__":
    # Execute the function
    asyncio.run(check_api()) 