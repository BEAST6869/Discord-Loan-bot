"""
Test UnbelievaBoat API functionality
"""

import asyncio
import config
import logging
import json
import os
import sys
from unbelievaboat_integration import UnbelievaBoatAPI

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("unbelievaboat_tester")

async def test_api():
    """Test the UnbelievaBoat API functionality"""
    logger.info(f"Testing UnbelievaBoat API token: {config.UNBELIEVABOAT['API_KEY'][:15]}...")
    
    # Try to get port configuration from environment
    unbelievaboat_port = None
    try:
        port_env = os.environ.get('UNBELIEVABOAT_PORT')
        if port_env:
            unbelievaboat_port = int(port_env)
            logger.info(f"Using UnbelievaBoat port from environment: {unbelievaboat_port}")
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid UNBELIEVABOAT_PORT environment variable: {e}")
    
    # Create API client with appropriate configuration and detailed debug level
    api = UnbelievaBoatAPI(
        api_key=config.UNBELIEVABOAT["API_KEY"],
        port=unbelievaboat_port,
        timeout=60  # Increased timeout for testing
    )
    
    # Get command line arguments
    if len(sys.argv) >= 3:
        guild_id = sys.argv[1]
        user_id = sys.argv[2]
    else:
        # Get inputs if not provided as arguments
        guild_id = input("Enter the guild ID to test with: ")
        user_id = input("Enter the user ID to test with: ")
    
    logger.info(f"Testing with guild ID: {guild_id}, user ID: {user_id}")
    
    try:
        # Step 1: Try to get user balance
        logger.info("\n=== Testing get_user_balance ===")
        balance = await api.get_user_balance(guild_id, user_id)
        
        if balance:
            logger.info(f"✅ Successfully got balance: {json.dumps(balance, indent=2)}")
            initial_cash = balance.get('cash', 0)
            logger.info(f"Current cash balance: {initial_cash}")
        else:
            logger.error(f"❌ Could not get user balance. This could indicate:")
            logger.error("   - The API token might be invalid")
            logger.error("   - The guild or user IDs are incorrect")
            logger.error("   - The UnbelievaBoat bot is not in the server")
            logger.error("   - The bot doesn't have permissions")
            return
        
        # Step 2: Try to add currency
        test_amount = 100
        logger.info(f"\n=== Testing add_currency with {test_amount} ===")
        add_result = await api.add_currency(
            guild_id, 
            user_id, 
            test_amount, 
            reason="API test"
        )
        
        if add_result:
            new_cash = add_result.get('cash', 0)
            logger.info(f"✅ Successfully added currency. New cash balance: {new_cash}")
            
            if new_cash - initial_cash == test_amount:
                logger.info(f"✅ Balance correctly increased by {test_amount}")
            else:
                logger.warning(f"⚠️ Balance changed by {new_cash - initial_cash}, not by expected {test_amount}")
        else:
            logger.error("❌ Failed to add currency")
            logger.error("   - This may be due to permission issues with the bot")
            logger.error("   - The UnbelievaBoat bot may not have permission to manage economy")
            return
            
        # Step 3: Try to remove currency
        logger.info(f"\n=== Testing remove_currency with {test_amount} ===")
        remove_result = await api.remove_currency(
            guild_id, 
            user_id, 
            test_amount, 
            reason="API test cleanup"
        )
        
        if remove_result:
            final_cash = remove_result.get('cash', 0)
            logger.info(f"✅ Successfully removed currency. Final cash balance: {final_cash}")
            
            if initial_cash == final_cash:
                logger.info("✅ Balance correctly restored to original amount")
            else:
                logger.warning(f"⚠️ Final balance {final_cash} differs from initial balance {initial_cash}")
        else:
            logger.error("❌ Failed to remove currency")
        
        # Clean up
        await api.close()
        
        # Overall assessment
        logger.info("\n=== Test Summary ===")
        if balance and add_result and remove_result:
            logger.info("✅ All API tests PASSED! The integration appears functional.")
        else:
            issues = []
            if not balance:
                issues.append("- Cannot retrieve balance")
            if not add_result:
                issues.append("- Cannot add currency")
            if not remove_result:
                issues.append("- Cannot remove currency")
            
            logger.error(f"❌ API tests FAILED with the following issues:")
            for issue in issues:
                logger.error(issue)
                
            logger.info("\nPossible solutions:")
            logger.info("1. Make sure UnbelievaBoat bot is in the server")
            logger.info("2. Verify the API token is correct")
            logger.info("3. Ensure UnbelievaBoat has proper permissions")
            logger.info("4. Check if the guild and user IDs are correct")
        
    except Exception as e:
        logger.error(f"Error during API tests: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await api.close()

if __name__ == "__main__":
    # Execute the function
    asyncio.run(test_api()) 