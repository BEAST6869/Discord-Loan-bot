import discord
from discord import app_commands
from discord.ext import commands
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server_settings

class SetAdminChannelCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="set_admin_channel", description="Set the channel for loan request notifications (Admin only)")
    @app_commands.describe(
        channel="The channel where loan notifications will be sent"
    )
    async def set_admin_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You don't have permission to use this command. Only administrators can set the admin channel.",
                ephemeral=True
            )
        
        guild_id = str(interaction.guild.id)
        channel_id = str(channel.id)
        
        # Update the server settings
        success = server_settings.set_admin_channel(guild_id, channel_id)
        
        if success:
            return await interaction.response.send_message(
                f"✅ Admin channel set to {channel.mention}. Loan request notifications will be sent here.",
                ephemeral=True
            )
        else:
            return await interaction.response.send_message(
                "❌ There was an error setting the admin channel. Please try again.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(SetAdminChannelCommand(bot)) 