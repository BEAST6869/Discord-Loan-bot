"""UnbelievaBoat API Integration"""

import aiohttp
import asyncio
import logging
import json
import os
from typing import Optional, Dict, Any, Union

logger = logging.getLogger("discord")

class UnbelievaBoatAPI:
    def __init__(self, api_key, host=None, port=None, timeout=10):
        """
        Initialize the API
        :param api_key: UnbelievaBoat API key
        :param host: API host (None for default)
        :param port: API port (None for default - 443)
        :param timeout: API timeout in seconds
        """
        self.api_key = str(api_key).strip()
        self.timeout = timeout
        self.session = None
        
        # Configure the host and port
        self.host = host if host else "unbelievaboat.com"
        
        # Default port is 443 for HTTPS
        self.port = port
        
        # Build base URL with proper port handling
        if self.port and self.port != 443:
            # Custom port for debug/testing
            self.base_url = f"https://{self.host}:{self.port}/api/v1"
            logger.info(f"Using custom port {self.port} for UnbelievaBoat API")
        else:
            # Standard HTTPS port (443)
            self.base_url = f"https://{self.host}/api/v1"
            logger.info(f"Using standard HTTPS port for UnbelievaBoat API")
        
        logger.info(f"UnbelievaBoat API initialized with base URL: {self.base_url}")
        
        # Headers include Authorization and Content-Type
        self.headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json"
        }
    
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
            # Ensure guild_id and user_id are strings
            guild_id = str(guild_id)
            user_id = str(user_id)
            
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
            # Ensure all inputs are properly typed
            guild_id = str(guild_id)
            user_id = str(user_id)
            
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
            
            try:
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
                            
                            # Log detailed response
                            logger.info(f"Full response: user_id={response_data.get('user_id')}, cash={response_data.get('cash')}, bank={response_data.get('bank')}, total={response_data.get('total')}, found={response_data.get('found')}")
                            
                            return response_data
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse response as JSON: {response_text}")
                            return None
                    elif status in (401, 403):
                        logger.error(f"API authentication error. Status: {status}")
                        logger.error(f"Error response: {response_text}")
                        
                        # Check if the token is expired/invalid
                        if "invalid token" in response_text.lower() or "expired" in response_text.lower():
                            logger.error("API token appears to be invalid or expired. Please check your token.")
                        elif "insufficient permissions" in response_text.lower():
                            logger.error("API token has insufficient permissions. Make sure it has write access.")
                            
                        return None
                    elif status == 404:
                        logger.error(f"Guild {guild_id} or user {user_id} not found")
                        logger.error(f"Error response: {response_text}")
                        return None
                    else:
                        logger.error(f"API error {status}: {response_text}")
                        
                        # Additional advice for common errors
                        if status == 429:
                            logger.error("Rate limit exceeded. The bot is making too many requests.")
                        elif status >= 500:
                            logger.error("UnbelievaBoat server error. The service may be experiencing issues.")
                            
                        return None
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Connection error: {str(e)}")
                logger.error("Check if the UnbelievaBoat API is accessible from your network.")
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
            # Ensure all inputs are properly typed
            guild_id = str(guild_id)
            user_id = str(user_id)
            
            # Validate inputs
            if not guild_id or not user_id:
                logger.error("Invalid guild_id or user_id")
                return None
                
            if not isinstance(amount, (int, float)) or amount <= 0:
                logger.error(f"Invalid amount: {amount}")
                return None
                
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
                response_text = await response.text()
                
                # Log response status
                logger.info(f"Remove currency request status: {status}")
                logger.info(f"Response body: {response_text}")
                
                # If 401 or 403, likely API token issue
                if status == 401 or status == 403:
                    logger.error("API authentication error. Check your API token.")
                    logger.error(f"Error response: {response_text}")
                    return None
                
                # If 404, likely guild or user not found
                if status == 404:
                    logger.error(f"Guild {guild_id} or user {user_id} not found")
                    logger.error(f"Error response: {response_text}")
                    return None
                
                # Check for other errors
                if status >= 400:
                    logger.error(f"API error {status}: {response_text}")
                    return None
                    
                try:
                    response_data = json.loads(response_text)
                    logger.info(f"Currency removed successfully. New balance: {response_data.get('cash', 'unknown')}")
                    return response_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse response as JSON: {response_text}")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"Request timed out after {self.timeout} seconds")
            return None
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error: {str(e)}")
            return None
        except Exception as error:
            logger.error(f"Error removing currency: {str(error)}")
            import traceback
            logger.error(traceback.format_exc())
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