#!/usr/bin/env python
"""
UnbelievaBoat API Diagnostic Tool

Usage:
  python diagnose_api.py [guild_id] [user_id] [test_amount]

This script tests the UnbelievaBoat API integration and helps diagnose any issues.
It performs get_balance and add_currency operations with detailed output.
"""

import asyncio
import sys
import logging
import json
import os
from unbelievaboat_integration import UnbelievaBoatAPI
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("diagnose_api")

async def run_diagnostics(guild_id=None, user_id=None, test_amount=100):
    """Run a series of diagnostic tests on the UnbelievaBoat API"""
    
    # Get API key from config
    api_key = config.UNBELIEVABOAT.get("API_KEY")
    
    # Check if API key is provided
    if not api_key:
        logger.error("No API key provided in config or environment variables.")
        logger.info("Please update the UNBELIEVABOAT_API_KEY environment variable or config.py file.")
        return False
    
    # Set default guild_id if not provided
    if not guild_id:
        guild_id = config.UNBELIEVABOAT.get("GUILD_ID")
        if not guild_id:
            logger.error("No guild_id provided as argument or in config.")
            logger.info("Please specify a guild_id as the first argument.")
            return False
    
    # Initialize API client
    try:
        logger.info(f"Initializing UnbelievaBoat API with token starting with: {api_key[:10]}...")
        
        # Try to get port from environment
        port = None
        port_env = os.environ.get('UNBELIEVABOAT_PORT')
        if port_env:
            try:
                port = int(port_env)
                logger.info(f"Using port from environment: {port}")
            except ValueError:
                logger.warning(f"Invalid UNBELIEVABOAT_PORT value: {port_env}")
        
        # Create API client
        api = UnbelievaBoatAPI(
            api_key=api_key,
            port=port,
            timeout=30
        )
        
        logger.info(f"API initialized with base URL: {api.base_url}")
        
        # Test 1: Check guild balance (doesn't require user_id)
        logger.info(f"TEST 1: Checking guild leaderboard for guild_id {guild_id}")
        guild_leaderboard = await api.get_leaderboard(guild_id, limit=5)
        
        if guild_leaderboard:
            logger.info(f"✅ Guild {guild_id} leaderboard retrieved successfully with {len(guild_leaderboard)} entries")
            for i, entry in enumerate(guild_leaderboard[:3], 1):
                logger.info(f"  User {i}: ID={entry.get('user_id')}, Cash={entry.get('cash')}, Bank={entry.get('bank')}")
        else:
            logger.error(f"❌ Failed to retrieve leaderboard for guild {guild_id}")
            logger.info("This suggests the bot cannot access guild data. Check API key permissions.")
            return False
        
        # If user_id provided, run user-specific tests
        if user_id:
            # Test 2: Get user balance
            logger.info(f"TEST 2: Getting balance for user {user_id} in guild {guild_id}")
            balance = await api.get_user_balance(guild_id, user_id)
            
            if balance:
                logger.info(f"✅ User balance: Cash={balance.get('cash')}, Bank={balance.get('bank')}, Total={balance.get('total')}")
            else:
                logger.error(f"❌ Failed to get balance for user {user_id}")
                logger.info("This suggests the API key doesn't have permission for this user or the user doesn't exist.")
                return False
            
            # If test_amount provided, test currency add/remove
            if test_amount:
                # Test 3: Add currency
                test_amount = int(test_amount)
                logger.info(f"TEST 3: Adding {test_amount} currency to user {user_id}")
                
                add_result = await api.add_currency(
                    guild_id,
                    user_id,
                    test_amount,
                    "API diagnostic test"
                )
                
                if add_result:
                    logger.info(f"✅ Successfully added {test_amount} currency")
                    logger.info(f"New balance: Cash={add_result.get('cash')}, Bank={add_result.get('bank')}, Total={add_result.get('total')}")
                    
                    # Test 4: Remove the same amount to avoid affecting balance
                    logger.info(f"TEST 4: Removing {test_amount} currency from user {user_id}")
                    
                    remove_result = await api.remove_currency(
                        guild_id,
                        user_id,
                        test_amount,
                        "API diagnostic test cleanup"
                    )
                    
                    if remove_result:
                        logger.info(f"✅ Successfully removed {test_amount} currency")
                        logger.info(f"Final balance: Cash={remove_result.get('cash')}, Bank={remove_result.get('bank')}, Total={remove_result.get('total')}")
                    else:
                        logger.error(f"❌ Failed to remove currency - user balance left with extra {test_amount}")
                        logger.info("This suggests the API key has add permission but not remove permission.")
                        return False
                else:
                    logger.error(f"❌ Failed to add {test_amount} currency to user {user_id}")
                    logger.info("This suggests the API key doesn't have write permission.")
                    return False
        
        # Close the API session
        await api.close()
        
        logger.info("✅ All available tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error during API diagnostics: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main entry point"""
    # Get command line arguments
    args = sys.argv[1:]
    guild_id = args[0] if len(args) > 0 else None
    user_id = args[1] if len(args) > 1 else None
    test_amount = int(args[2]) if len(args) > 2 else 100
    
    # Print usage
    if not guild_id:
        print("Usage: python diagnose_api.py [guild_id] [user_id] [test_amount]")
        print("\nguild_id: Required - Discord server ID")
        print("user_id: Optional - Discord user ID to test")
        print("test_amount: Optional - Amount to use for testing (default: 100)")
        sys.exit(1)
    
    # Run diagnostics
    logger.info(f"Starting UnbelievaBoat API diagnostics...")
    logger.info(f"Guild ID: {guild_id}")
    if user_id:
        logger.info(f"User ID: {user_id}")
    if test_amount:
        logger.info(f"Test amount: {test_amount}")
    
    # Run the async function
    success = asyncio.run(run_diagnostics(guild_id, user_id, test_amount))
    
    # Exit with appropriate status code
    if success:
        logger.info("✅ Diagnostics passed!")
        sys.exit(0)
    else:
        logger.error("❌ Diagnostics failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 