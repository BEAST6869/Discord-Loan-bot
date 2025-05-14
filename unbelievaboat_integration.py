"""UnbelievaBoat API Integration"""

import aiohttp
import asyncio
import logging
import json
import os
from typing import Optional, Dict, Any, Union

logger = logging.getLogger("discord")

class UnbelievaBoatAPI:
    def __init__(self, api_key, port: Optional[int] = None, timeout: int = 30, 
                 max_connections: int = 100, ssl_verify: bool = True):
        # Clean up the API key - remove any whitespace and ensure it's a string
        self.api_key = str(api_key).strip()
        self.base_url = 'https://unbelievaboat.com/api/v1'
        self.timeout = timeout
        self.max_connections = max_connections
        self.ssl_verify = ssl_verify
        
        # Only modify URL if port is explicitly provided and valid
        if port is not None and isinstance(port, int) and port > 0:
            self.port = port
            # Extract protocol and domain from base URL
            try:
                url_parts = self.base_url.split('://')
                if len(url_parts) == 2:
                    protocol = url_parts[0]
                    domain_parts = url_parts[1].split('/', 1)
                    domain = domain_parts[0]
                    path = domain_parts[1] if len(domain_parts) > 1 else ''
                    self.base_url = f"{protocol}://{domain}:{port}/{path}"
                    logger.info(f"Using custom port {port}, new base URL: {self.base_url}")
                else:
                    logger.warning(f"Invalid base URL format: {self.base_url}, ignoring port configuration")
            except Exception as e:
                logger.error(f"Error setting custom port: {e}")
                # Keep the original base_url if there's an error
        else:
            self.port = None
        
        self.headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        self.session = None
        logger.info(f"UnbelievaBoat API initialized with token starting with: {self.api_key[:10]}...")
        logger.info(f"Using base URL: {self.base_url}")
    
    async def _ensure_session(self):
        """Ensure an aiohttp session exists with proper configuration"""
        if self.session is None or self.session.closed:
            try:
                # Configure TCP connector for better connection management
                connector = aiohttp.TCPConnector(
                    limit=self.max_connections,
                    ssl=self.ssl_verify,
                    force_close=False,
                    enable_cleanup_closed=True
                )
                
                # Configure timeout for all requests
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                
                # Create session with the configured connector and timeout
                self.session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    headers=self.headers  # Apply headers to all requests by default
                )
                logger.info(f"Created new aiohttp session with {self.max_connections} max connections")
            except Exception as e:
                logger.error(f"Error creating aiohttp session: {e}")
                # Fallback to a simple session if the configured one fails
                self.session = aiohttp.ClientSession(headers=self.headers)
                logger.info("Created fallback aiohttp session after error")
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
            
            async with session.get(url) as response:
                status = response.status
                response_text = await response.text()
                
                logger.info(f"Response status: {status}")
                logger.info(f"Response body: {response_text}")
                
                if status == 200:
                    try:
                        response_data = json.loads(response_text)
                        logger.info(f"Got balance data: {json.dumps(response_data)[:100]}...")
                        return response_data
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse response as JSON: {response_text}")
                        return None
                elif status in (401, 403):
                    logger.error("API authentication error. Check your API token.")
                    logger.error(f"Error response: {response_text}")
                    return None
                elif status == 404:
                    logger.error(f"Guild {guild_id} or user {user_id} not found")
                    logger.error(f"Error response: {response_text}")
                    return None
                else:
                    logger.error(f"API error {status}: {response_text}")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"Request timed out after {self.timeout} seconds")
            return None
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error: {str(e)}")
            return None
        except Exception as error:
            logger.error(f"Error getting user balance: {str(error)}")
            import traceback
            logger.error(traceback.format_exc())
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
            # Validate inputs
            if not guild_id or not user_id:
                logger.error("Invalid guild_id or user_id")
                return None
                
            if not isinstance(amount, (int, float)) or amount <= 0:
                logger.error(f"Invalid amount: {amount}")
                return None

            logger.info(f"Adding {amount} to user {user_id} in guild {guild_id}")
            session = await self._ensure_session()
            
            # Use the correct endpoint format
            url = f"{self.base_url}/guilds/{guild_id}/users/{user_id}"
            logger.info(f"Making PATCH request to: {url}")
            
            # Prepare request data
            request_data = {
                'cash': int(amount),  # Ensure amount is an integer
                'reason': str(reason)  # Ensure reason is a string
            }
            
            # Log request details for debugging
            logger.info(f"Request data: {json.dumps(request_data)}")
            
            async with session.patch(
                url,
                json=request_data
            ) as response:
                status = response.status
                response_text = await response.text()
                
                # Log full response for debugging
                logger.info(f"Response status: {status}")
                logger.info(f"Response body: {response_text}")
                
                # Handle different response statuses
                if status == 200:
                    try:
                        response_data = json.loads(response_text)
                        logger.info(f"Currency added successfully. New balance: {response_data.get('cash', 'unknown')}")
                        return response_data
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse response as JSON: {response_text}")
                        return None
                elif status in (401, 403):
                    logger.error(f"API authentication error. Status: {status}")
                    logger.error(f"Error response: {response_text}")
                    return None
                elif status == 404:
                    logger.error(f"Guild {guild_id} or user {user_id} not found")
                    logger.error(f"Error response: {response_text}")
                    return None
                else:
                    logger.error(f"API error {status}: {response_text}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.error(f"Request timed out after {self.timeout} seconds")
            return None
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error: {str(e)}")
            return None
        except Exception as error:
            logger.error(f"Error adding currency: {str(error)}")
            import traceback
            logger.error(traceback.format_exc())
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
        except asyncio.TimeoutError:
            logger.error(f"Request timed out after {self.timeout} seconds")
            return None
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error: {str(e)}")
            return None
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
        except asyncio.TimeoutError:
            logger.error(f"Request timed out after {self.timeout} seconds")
            return None
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error: {str(e)}")
            return None
        except Exception as error:
            logger.error(f"Error fetching leaderboard: {str(error)}")
            return None
            
    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("Closed UnbelievaBoat API session") 