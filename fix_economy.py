"""
Utility to check and fix economy integration data in the bot
"""

import asyncio
import json
import os
import logging
import sys
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("economy_fixer")

# Import modules
try:
    import config
    from unbelievaboat_integration import UnbelievaBoatAPI
    import bot  # This will load the bot data
except ImportError as e:
    logger.error(f"Error importing required modules: {e}")
    sys.exit(1)

async def check_economy_integration(guild_id, user_id):
    """Check economy integration for a specific guild and user"""
    logger.info(f"Checking economy integration for guild {guild_id}, user {user_id}")
    
    # Initialize UnbelievaBoat API
    api = UnbelievaBoatAPI(
        api_key=config.UNBELIEVABOAT["API_KEY"],
        timeout=30
    )
    
    try:
        # Check basic API functionality
        logger.info("Testing user balance retrieval...")
        balance = await api.get_user_balance(guild_id, user_id)
        
        if balance:
            logger.info(f"✅ API connection successful, user balance: {json.dumps(balance, indent=2)}")
        else:
            logger.error("❌ Cannot retrieve user balance, API integration not working")
            return False
            
        # Check loan data
        logger.info("\nChecking loan database...")
        loan_database = getattr(bot, 'loan_database', None)
        
        if not loan_database:
            logger.error("❌ Bot loan database not found or not initialized")
            return False
            
        # Log database contents
        logger.info(f"Active loans: {len(loan_database.get('loans', []))}")
        logger.info(f"Loan requests: {len(loan_database.get('loan_requests', []))}")
        logger.info(f"Loan history: {len(loan_database.get('history', []))}")
        
        # Check loans for the specific guild
        guild_loans = [
            loan for loan in loan_database.get('loans', [])
            if loan.get('guild_id') == guild_id
        ]
        logger.info(f"Active loans in guild {guild_id}: {len(guild_loans)}")
        
        # Check loans for the specific user in the guild
        user_loans = [
            loan for loan in guild_loans
            if loan.get('user_id') == user_id
        ]
        logger.info(f"Active loans for user {user_id} in guild {guild_id}: {len(user_loans)}")
        
        # Debug loan details if any
        if user_loans:
            for i, loan in enumerate(user_loans):
                logger.info(f"\nLoan #{i+1} Details:")
                logger.info(f"  ID: {loan.get('id')}")
                logger.info(f"  Amount: {loan.get('amount')}")
                logger.info(f"  Status: {loan.get('status')}")
                logger.info(f"  Due date: {loan.get('due_date')}")
                
                # Check if UnbelievaBoat integration data exists
                if 'unbelievaboat' in loan:
                    logger.info(f"  ✅ UnbelievaBoat integration data found: {json.dumps(loan['unbelievaboat'], indent=2)}")
                else:
                    logger.warning(f"  ⚠️ No UnbelievaBoat integration data found for this loan")
        
        return True
            
    except Exception as e:
        logger.error(f"Error checking economy integration: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        await api.close()

async def fix_loan_data(guild_id, user_id, loan_id=None):
    """Try to fix loan data for a specific loan ID or all loans for a user"""
    logger.info(f"Attempting to fix loan data for guild {guild_id}, user {user_id}")
    
    # Initialize UnbelievaBoat API
    api = UnbelievaBoatAPI(
        api_key=config.UNBELIEVABOAT["API_KEY"],
        timeout=30
    )
    
    try:
        # Get loan database
        loan_database = getattr(bot, 'loan_database', None)
        
        if not loan_database:
            logger.error("❌ Bot loan database not found or not initialized")
            return False
            
        # Find loans to fix
        loans_to_fix = []
        
        if loan_id:
            # Find specific loan
            for loan in loan_database.get('loans', []):
                if (loan.get('id') == loan_id and 
                    loan.get('user_id') == user_id and 
                    loan.get('guild_id') == guild_id):
                    loans_to_fix.append(loan)
                    break
        else:
            # Find all loans for user in guild
            loans_to_fix = [
                loan for loan in loan_database.get('loans', [])
                if loan.get('user_id') == user_id and loan.get('guild_id') == guild_id
            ]
            
        if not loans_to_fix:
            logger.error(f"❌ No loans found to fix for user {user_id} in guild {guild_id}")
            return False
            
        # Fix each loan
        fixed_count = 0
        for loan in loans_to_fix:
            loan_id = loan.get('id')
            logger.info(f"\nFixing loan {loan_id}...")
            
            # Check if UnbelievaBoat integration data exists
            if 'unbelievaboat' not in loan:
                # Add integration data
                logger.info(f"Adding UnbelievaBoat integration data for loan {loan_id}")
                
                # Get current balance
                balance = await api.get_user_balance(guild_id, user_id)
                
                if balance:
                    # Add integration data
                    loan['unbelievaboat'] = {
                        "transaction_processed": True,
                        "balance": balance.get('cash', 0)
                    }
                    fixed_count += 1
                    logger.info(f"✅ Fixed loan {loan_id}")
                else:
                    logger.error(f"❌ Could not get balance for user {user_id}")
            else:
                logger.info(f"Loan {loan_id} already has UnbelievaBoat integration data")
                
        logger.info(f"\nFixed {fixed_count} out of {len(loans_to_fix)} loans")
        return fixed_count > 0
            
    except Exception as e:
        logger.error(f"Error fixing loan data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        await api.close()

if __name__ == "__main__":
    # Check if guild and user IDs are provided
    if len(sys.argv) < 3:
        print("Usage: python fix_economy.py <guild_id> <user_id> [loan_id]")
        sys.exit(1)
        
    guild_id = sys.argv[1]
    user_id = sys.argv[2]
    loan_id = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Ask for confirmation
    print(f"This will check/fix economy integration for guild {guild_id}, user {user_id}")
    if loan_id:
        print(f"Will focus on loan ID: {loan_id}")
        
    confirm = input("Continue? (y/n): ").lower()
    if confirm != 'y':
        print("Operation cancelled")
        sys.exit(0)
        
    # Run checks
    print("\nRunning economy integration check...")
    asyncio.run(check_economy_integration(guild_id, user_id))
    
    # Ask if user wants to fix issues
    fix_confirm = input("\nDo you want to fix any detected issues? (y/n): ").lower()
    if fix_confirm == 'y':
        asyncio.run(fix_loan_data(guild_id, user_id, loan_id))
    else:
        print("Fix operation cancelled") 