#!/usr/bin/env python
"""
UnbelievaBoat API Diagnostic Tool

Usage:
  python diagnose_api.py [guild_id] [user_id] [test_amount]

This script tests the UnbelievaBoat API integration and helps diagnose any issues.
"""

import asyncio
import sys
import logging
import os
from unbelievaboat_integration import UnbelievaBoatAPI
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("diagnose_api")

async def run_diagnostics(guild_id, user_id=None, test_amount=100):
    """Run a series of diagnostic tests on the UnbelievaBoat API"""
    
    print(f"\n===== UnbelievaBoat API Diagnostics =====")
    print(f"Guild ID: {guild_id}")
    if user_id:
        print(f"User ID: {user_id}")
    print(f"Test amount: {test_amount}")
    print("=======================================\n")
    
    # Get API key from config
    api_key = config.UNBELIEVABOAT.get("API_KEY")
    
    # Check if API key is provided
    if not api_key:
        print("❌ ERROR: No API key provided in config or environment variables.")
        return False
    
    # Initialize API client
    try:
        print(f"🔑 API Key: {api_key[:10]}...")
        
        # Create API client
        api = UnbelievaBoatAPI(
            api_key=api_key,
            port=None,
            timeout=30
        )
        
        print(f"📡 Base URL: {api.base_url}")
        
        # Test 1: Check guild balance
        print("\n1️⃣ TEST 1: Checking guild leaderboard...")
        guild_leaderboard = await api.get_leaderboard(guild_id, limit=5)
        
        if guild_leaderboard:
            print(f"✅ Guild leaderboard retrieved successfully!")
            print(f"   Top users: {len(guild_leaderboard)} entries found")
        else:
            print(f"❌ Failed to retrieve leaderboard for guild {guild_id}")
            print("   This may indicate the API key doesn't have access to this guild.")
            return False
        
        # If user_id provided, run user-specific tests
        if user_id:
            # Test 2: Get user balance
            print(f"\n2️⃣ TEST 2: Getting balance for user {user_id}...")
            balance = await api.get_user_balance(guild_id, user_id)
            
            if balance:
                print(f"✅ User balance retrieved successfully!")
                print(f"   Cash: {balance.get('cash', 0)}")
                print(f"   Bank: {balance.get('bank', 0)}")
                print(f"   Total: {balance.get('total', 0)}")
            else:
                print(f"❌ Failed to get balance for user {user_id}")
                print("   This may indicate the user does not exist in this guild or the API has issues.")
                return False
            
            # Test 3: Add currency
            test_amount = int(test_amount)
            print(f"\n3️⃣ TEST 3: Adding {test_amount} currency to user {user_id}...")
            
            add_result = await api.add_currency(
                guild_id,
                user_id,
                test_amount,
                "API diagnostic test"
            )
            
            if add_result:
                print(f"✅ Successfully added {test_amount} currency!")
                print(f"   New cash balance: {add_result.get('cash', 0)}")
                
                # Test 4: Remove the same amount
                print(f"\n4️⃣ TEST 4: Removing {test_amount} currency from user {user_id}...")
                
                remove_result = await api.remove_currency(
                    guild_id,
                    user_id,
                    test_amount,
                    "API diagnostic test cleanup"
                )
                
                if remove_result:
                    print(f"✅ Successfully removed {test_amount} currency!")
                    print(f"   Final cash balance: {remove_result.get('cash', 0)}")
                else:
                    print(f"❌ Failed to remove currency")
                    print("   This suggests the API key has add permission but not remove permission.")
                    return False
            else:
                print(f"❌ Failed to add {test_amount} currency to user {user_id}")
                print("   This suggests the API key doesn't have write permission.")
                return False
        
        # Close the API session
        await api.close()
        
        print("\n✅ All tests PASSED! The UnbelievaBoat API integration appears to be working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during API diagnostics: {str(e)}")
        return False

def main():
    """Main entry point"""
    # Get command line arguments
    args = sys.argv[1:]
    
    if len(args) < 1:
        print("Usage: python diagnose_api.py [guild_id] [user_id] [test_amount]")
        print("\nguild_id: Required - Discord server ID")
        print("user_id: Optional - Discord user ID to test")
        print("test_amount: Optional - Amount to use for testing (default: 100)")
        sys.exit(1)
    
    # Parse arguments
    guild_id = args[0]
    user_id = args[1] if len(args) > 1 else None
    test_amount = int(args[2]) if len(args) > 2 else 100
    
    try:
        # Run the async function
        success = asyncio.run(run_diagnostics(guild_id, user_id, test_amount))
        
        # Exit with appropriate status code
        if success:
            print("\n✅ Diagnostics passed!")
            sys.exit(0)
        else:
            print("\n❌ Diagnostics failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unhandled error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 