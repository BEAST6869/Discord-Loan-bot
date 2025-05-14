"""UnbelievaBoat API Integration"""

import aiohttp
import asyncio
import logging
import json

logger = logging.getLogger("discord")

class UnbelievaBoatAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = 'https://unbelievaboat.com/api/v1'
        self.headers = {
            'Authorization': api_key,  # JWT tokens are sent as-is, not with Bearer prefix
            'Content-Type': 'application/json'
        }
        self.session = None
        logger.info(f"UnbelievaBoat API initialized with token starting with: {api_key[:10]}...")
    
    async def _ensure_session(self):
        """Ensure an aiohttp session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
            logger.info("Created new aiohttp session for UnbelievaBoat API")
        return self.session

    async def get_user_balance(self, guild_id, user_id):
        """
        Get a user's balance
        :param guild_id: Discord guild ID
        :param user_id: Discord user ID
        :return: User's balance information or None if error
        """
        try:
            logger.info(f"Getting balance for user {user_id} in guild {guild_id}")
            session = await self._ensure_session()
            
            url = f"{self.base_url}/guilds/{guild_id}/users/{user_id}"
            logger.info(f"Making GET request to: {url}")
            
            async with session.get(
                url,
                headers=self.headers
            ) as response:
                status = response.status
                
                # Log response status
                logger.info(f"Balance request status: {status}")
                
                # If 401 or 403, likely API token issue
                if status == 401 or status == 403:
                    logger.error("API authentication error. Check your API token.")
                    return None
                
                # If 404, likely guild or user not found
                if status == 404:
                    logger.error(f"Guild {guild_id} or user {user_id} not found")
                    return None
                
                # Check for other errors
                if status >= 400:
                    text = await response.text()
                    logger.error(f"API error {status}: {text}")
                    return None
                    
                response_data = await response.json()
                logger.info(f"Got balance data: {json.dumps(response_data)[:100]}...")
                return response_data
        except Exception as error:
            logger.error(f"Error getting user balance: {str(error)}")
            return None

    async def add_currency(self, guild_id, user_id, amount, reason=''):
        """
        Add currency to a user's balance
        :param guild_id: Discord guild ID
        :param user_id: Discord user ID
        :param amount: Amount to add (positive integer)
        :param reason: Reason for transaction (optional)
        :return: Updated balance information or None if error
        """
        try:
            logger.info(f"Adding {amount} to user {user_id} in guild {guild_id}")
            session = await self._ensure_session()
            
            url = f"{self.base_url}/guilds/{guild_id}/users/{user_id}"
            logger.info(f"Making PATCH request to: {url} with data: cash={amount}, reason={reason}")
            
            async with session.patch(
                url,
                headers=self.headers,
                json={
                    'cash': amount,
                    'reason': reason
                }
            ) as response:
                status = response.status
                
                # Log response status
                logger.info(f"Add currency request status: {status}")
                
                # If 401 or 403, likely API token issue
                if status == 401 or status == 403:
                    logger.error("API authentication error. Check your API token.")
                    text = await response.text()
                    logger.error(f"Error response: {text}")
                    return None
                
                # If 404, likely guild or user not found
                if status == 404:
                    logger.error(f"Guild {guild_id} or user {user_id} not found")
                    text = await response.text()
                    logger.error(f"Error response: {text}")
                    return None
                
                # Check for other errors
                if status >= 400:
                    text = await response.text()
                    logger.error(f"API error {status}: {text}")
                    return None
                    
                response_data = await response.json()
                logger.info(f"Currency added successfully. New balance: {response_data.get('cash', 'unknown')}")
                return response_data
        except Exception as error:
            logger.error(f"Error adding currency: {str(error)}")
            return None

    async def remove_currency(self, guild_id, user_id, amount, reason=''):
        """
        Remove currency from a user's balance
        :param guild_id: Discord guild ID
        :param user_id: Discord user ID
        :param amount: Amount to remove (positive integer)
        :param reason: Reason for transaction (optional)
        :return: Updated balance information or None if error
        """
        try:
            logger.info(f"Removing {amount} from user {user_id} in guild {guild_id}")
            session = await self._ensure_session()
            
            url = f"{self.base_url}/guilds/{guild_id}/users/{user_id}"
            logger.info(f"Making PATCH request to: {url} with data: cash=-{amount}, reason={reason}")
            
            async with session.patch(
                url,
                headers=self.headers,
                json={
                    'cash': -amount,  # Negative amount to remove
                    'reason': reason
                }
            ) as response:
                status = response.status
                
                # Log response status
                logger.info(f"Remove currency request status: {status}")
                
                # If 401 or 403, likely API token issue
                if status == 401 or status == 403:
                    logger.error("API authentication error. Check your API token.")
                    text = await response.text()
                    logger.error(f"Error response: {text}")
                    return None
                
                # If 404, likely guild or user not found
                if status == 404:
                    logger.error(f"Guild {guild_id} or user {user_id} not found")
                    text = await response.text()
                    logger.error(f"Error response: {text}")
                    return None
                
                # Check for other errors
                if status >= 400:
                    text = await response.text()
                    logger.error(f"API error {status}: {text}")
                    return None
                    
                response_data = await response.json()
                logger.info(f"Currency removed successfully. New balance: {response_data.get('cash', 'unknown')}")
                return response_data
        except Exception as error:
            logger.error(f"Error removing currency: {str(error)}")
            return None

    async def get_leaderboard(self, guild_id, sort_by='total', limit=10):
        """
        Get the leaderboard for a guild
        :param guild_id: Discord guild ID
        :param sort_by: Field to sort by (cash, bank, total)
        :param limit: Maximum number of users to return (default 10)
        :return: Leaderboard entries or None if error
        """
        try:
            logger.info(f"Getting leaderboard for guild {guild_id}")
            session = await self._ensure_session()
            
            url = f"{self.base_url}/guilds/{guild_id}/users"
            logger.info(f"Making GET request to: {url} with params: sort={sort_by}, limit={limit}")
            
            async with session.get(
                url,
                headers=self.headers,
                params={
                    'sort': sort_by,
                    'limit': limit
                }
            ) as response:
                status = response.status
                
                # Log response status
                logger.info(f"Leaderboard request status: {status}")
                
                # Check for errors
                if status >= 400:
                    text = await response.text()
                    logger.error(f"API error {status}: {text}")
                    return None
                    
                response_data = await response.json()
                logger.info(f"Got leaderboard data with {len(response_data)} entries")
                return response_data
        except Exception as error:
            logger.error(f"Error fetching leaderboard: {str(error)}")
            return None
            
    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("Closed UnbelievaBoat API session") 