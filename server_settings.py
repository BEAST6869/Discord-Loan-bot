"""
Server Settings Management

This module handles loading, saving, and managing server-specific settings.
"""

import json
import os
import config
import logging

logger = logging.getLogger("discord")


def load_settings():
    """Load server settings from file"""
    try:
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Check if the settings file exists
        if os.path.exists("data/server_settings.json"):
            with open("data/server_settings.json", "r") as f:
                settings = json.load(f)
                
            # Update the config
            config.SERVER_SETTINGS = settings
            logger.info("Loaded server settings from file")
        else:
            logger.info("No server settings file found, using defaults")
    except Exception as e:
        logger.error(f"Error loading server settings: {e}")


def save_settings():
    """Save server settings to file"""
    try:
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Save to file
        with open("data/server_settings.json", "w") as f:
            json.dump(config.SERVER_SETTINGS, f, indent=2)
            
        logger.info("Server settings saved to file")
    except Exception as e:
        logger.error(f"Error saving server settings: {e}")


def get_guild_settings(guild_id):
    """
    Get settings for a specific guild
    :param guild_id: Discord guild ID as string
    :return: Guild settings dict or empty dict if not found
    """
    guild_id = str(guild_id)  # Ensure it's a string
    return config.SERVER_SETTINGS.get(guild_id, {})


def save_guild_settings(guild_id, settings):
    """
    Save settings for a specific guild
    :param guild_id: Discord guild ID as string
    :param settings: Dict of settings for the guild
    :return: True if successful
    """
    guild_id = str(guild_id)  # Ensure it's a string
    
    # Update the settings in memory
    config.SERVER_SETTINGS[guild_id] = settings
    
    # Save to file
    save_settings()
    
    return True


def set_captain_role(guild_id, role_id):
    """
    Set the captain role for a guild
    :param guild_id: Discord guild ID as string
    :param role_id: Discord role ID as string
    """
    guild_id = str(guild_id)  # Ensure it's a string
    role_id = str(role_id)    # Ensure it's a string
    
    # Ensure the guild exists in settings
    if guild_id not in config.SERVER_SETTINGS:
        config.SERVER_SETTINGS[guild_id] = {}
    
    # Update the captain role
    config.SERVER_SETTINGS[guild_id]["captain_role_id"] = role_id
    
    # Save the changes
    save_settings()
    
    return True


def set_max_loan_amount(guild_id, amount):
    """
    Set the maximum loan amount for a guild
    :param guild_id: Discord guild ID as string
    :param amount: Maximum loan amount as integer
    """
    guild_id = str(guild_id)  # Ensure it's a string
    amount = int(amount)      # Ensure it's an integer
    
    # Ensure the guild exists in settings
    if guild_id not in config.SERVER_SETTINGS:
        config.SERVER_SETTINGS[guild_id] = {}
    
    # Update the max loan amount
    config.SERVER_SETTINGS[guild_id]["max_loan_amount"] = amount
    
    # Save the changes
    save_settings()
    
    return True


def set_max_repayment_days(guild_id, days):
    """
    Set the maximum repayment days for a guild
    :param guild_id: Discord guild ID as string
    :param days: Maximum repayment days as integer
    """
    guild_id = str(guild_id)  # Ensure it's a string
    days = int(days)          # Ensure it's an integer
    
    # Ensure the guild exists in settings
    if guild_id not in config.SERVER_SETTINGS:
        config.SERVER_SETTINGS[guild_id] = {}
    
    # Update the max repayment days
    config.SERVER_SETTINGS[guild_id]["max_repayment_days"] = days
    
    # Save the changes
    save_settings()
    
    return True


def get_captain_role(guild_id):
    """
    Get the captain role ID for a guild
    :param guild_id: Discord guild ID as string
    :return: Captain role ID as string or None if not set
    """
    guild_id = str(guild_id)  # Ensure it's a string
    guild_settings = get_guild_settings(guild_id)
    return guild_settings.get("captain_role_id", None)


def get_max_loan_amount(guild_id):
    """
    Get the maximum loan amount for a guild
    :param guild_id: Discord guild ID as string
    :return: Maximum loan amount as integer or default if not set
    """
    guild_id = str(guild_id)  # Ensure it's a string
    guild_settings = get_guild_settings(guild_id)
    # Set a significantly high default to make it effectively unlimited unless restricted
    return guild_settings.get("max_loan_amount", 1000000000)  # Default: 1 billion


def get_max_repayment_days(guild_id):
    """
    Get the maximum repayment days for a guild
    :param guild_id: Discord guild ID as string
    :return: Maximum repayment days as integer or default (7) if not set
    """
    guild_id = str(guild_id)  # Ensure it's a string
    guild_settings = get_guild_settings(guild_id)
    return guild_settings.get("max_repayment_days", 7)  # Default: 7 days


def check_is_captain(guild_id, member):
    """
    Check if a member has the captain role
    :param guild_id: Discord guild ID
    :param member: Discord member object
    :return: True if member has captain role, False otherwise
    """
    captain_role_id = get_captain_role(guild_id)
    
    # If no captain role is set, allow everyone
    if not captain_role_id:
        return True
    
    # Convert to strings for comparison
    member_role_ids = [str(role.id) for role in member.roles]
    
    # Check if member has the captain role
    return captain_role_id in member_role_ids


def set_admin_channel(guild_id, channel_id):
    """
    Set the admin channel where loan request notifications will be sent
    :param guild_id: Discord guild ID as string
    :param channel_id: Discord channel ID as string
    :return: True if successful, False otherwise
    """
    guild_id = str(guild_id)  # Ensure it's a string
    channel_id = str(channel_id)  # Ensure it's a string
    
    # Get current settings
    guild_settings = get_guild_settings(guild_id)
    
    # Update settings
    guild_settings["admin_channel"] = channel_id
    
    # Save settings
    return save_guild_settings(guild_id, guild_settings)


def get_admin_channel(guild_id):
    """
    Get the admin channel ID for a guild
    :param guild_id: Discord guild ID as string
    :return: Channel ID as string or None if not set
    """
    guild_id = str(guild_id)  # Ensure it's a string
    guild_settings = get_guild_settings(guild_id)
    return guild_settings.get("admin_channel", None)


def set_approval_roles(guild_id, role_ids):
    """
    Set the roles that can approve loan requests
    :param guild_id: Discord guild ID as string
    :param role_ids: List of Discord role IDs as strings
    :return: True if successful, False otherwise
    """
    guild_id = str(guild_id)  # Ensure it's a string
    
    # Ensure guild exists in settings
    if guild_id not in config.SERVER_SETTINGS:
        config.SERVER_SETTINGS[guild_id] = {}
    
    # Update approval roles
    config.SERVER_SETTINGS[guild_id]["approval_roles"] = role_ids
    
    # Save settings
    save_settings()
    
    return True


def get_approval_roles(guild_id):
    """
    Get the roles that can approve loan requests
    :param guild_id: Discord guild ID as string
    :return: List of role IDs as strings or empty list if not set
    """
    guild_id = str(guild_id)  # Ensure it's a string
    guild_settings = get_guild_settings(guild_id)
    return guild_settings.get("approval_roles", []) 