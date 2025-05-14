"""
Generate an invite link for the bot to join any guild
"""

import discord
import config

def generate_invite_link():
    """Generate an invite link for the bot to join any guild"""
    
    # Get the client ID from config
    client_id = config.CLIENT_ID
    
    # Define necessary permissions for the bot
    permissions = discord.Permissions(
        # Basic permissions
        view_channel=True,
        send_messages=True,
        embed_links=True,
        attach_files=True,
        read_message_history=True,
        use_external_emojis=True,
        
        # Commands permissions
        use_application_commands=True,
        
        # Additional permissions for better functionality
        add_reactions=True,
        manage_messages=True  # For removing buttons after repayment
    )
    
    # Create the OAuth2 URL with both bot and applications.commands scopes
    invite_url = discord.utils.oauth_url(
        client_id,
        permissions=permissions,
        scopes=("bot", "applications.commands")
    )
    
    print("\n=== DISCORD BOT INVITE LINK ===")
    print(f"Use this link to add the bot to any guild:")
    print(invite_url)
    print("\nAfter adding the bot to your server, run deploy_commands.py to register the commands.")
    print("Then start the bot by running bot.py")
    print("===============================\n")

if __name__ == "__main__":
    generate_invite_link() 