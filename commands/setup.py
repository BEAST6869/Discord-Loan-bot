"""
Setup commands for configuring the bot in a server
"""

import discord
from discord import app_commands
from discord.ext import commands
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server_settings
import config
import logging

logger = logging.getLogger("discord")


class SetupCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="crew_captain_role", description="Set which role can request loans (Admin only)")
    @app_commands.describe(
        role="The role that can request loans (typically a Captain role)"
    )
    async def set_captain_role(self, interaction: discord.Interaction, role: discord.Role):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You need administrator permissions to use this command.",
                ephemeral=True
            )
        
        try:
            # Set the captain role
            guild_id = str(interaction.guild.id)
            role_id = str(role.id)
            
            server_settings.set_captain_role(guild_id, role_id)
            
            # Respond with confirmation
            embed = discord.Embed(
                title="✅ Captain Role Set",
                description=f"The {role.mention} role can now request loans in this server.",
                color=0x00FF00
            )
            
            embed.add_field(
                name="How it works",
                value="Only members with this role can use the `/loan` command.",
                inline=False
            )
            
            embed.add_field(
                name="To change",
                value="Run this command again with a different role.",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
            
            logger.info(f"Captain role set to {role.name} (ID: {role_id}) in guild {interaction.guild.name} (ID: {guild_id})")
            
        except Exception as error:
            logger.error(f"Error setting captain role: {str(error)}")
            await interaction.response.send_message(
                f"There was an error setting the captain role: {str(error)}",
                ephemeral=True
            )
    
    @app_commands.command(name="view_settings", description="View current server settings for the loan bot")
    async def view_settings(self, interaction: discord.Interaction):
        """Command to view server settings"""
        try:
            # Check if interaction is already responded to
            if interaction.response.is_done():
                logger.warning("Interaction already acknowledged in view_settings command, using followup instead")
                send_message = interaction.followup.send
            else:
                send_message = interaction.response.send_message
            
            # Get guild ID
            guild_id = str(interaction.guild.id)
            
            # Create an embed with all server settings
            embed = discord.Embed(
                title="⚙️ Loan Bot Settings",
                description="Current server configuration",
                color=0x0099FF
            )
            
            # Get captain role
            captain_role_id = server_settings.get_captain_role(guild_id)
            captain_role = None
            if captain_role_id:
                captain_role = interaction.guild.get_role(int(captain_role_id))
            
            captain_info = f"{captain_role.mention if captain_role else 'Not set'}"
            embed.add_field(name="Captain Role", value=captain_info, inline=True)
            
            # Get max loan amount
            max_loan = server_settings.get_max_loan_amount(guild_id)
            embed.add_field(
                name="Max Loan Amount",
                value=f"{max_loan:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
                inline=True
            )
            
            # Get max repayment days
            max_days = server_settings.get_max_repayment_days(guild_id)
            max_days_display = f"{max_days} days" if max_days < 9999 else "Unlimited"
            embed.add_field(name="Max Repayment Period", value=max_days_display, inline=True)
            
            # Get admin channel
            admin_channel_id = server_settings.get_admin_channel(guild_id)
            admin_channel = None
            if admin_channel_id:
                admin_channel = interaction.guild.get_channel(int(admin_channel_id))
            
            admin_channel_info = f"{admin_channel.mention if admin_channel else 'Not set'}"
            embed.add_field(name="Admin Channel", value=admin_channel_info, inline=True)
            
            # Get approval roles
            approval_roles = server_settings.get_approval_roles(guild_id)
            approval_roles_info = ""
            
            if approval_roles:
                role_mentions = []
                for role_id in approval_roles:
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        role_mentions.append(role.mention)
                
                if role_mentions:
                    approval_roles_info = ", ".join(role_mentions)
                else:
                    approval_roles_info = "No valid roles"
            else:
                approval_roles_info = "Not set (admin only)"
            
            embed.add_field(name="Approval Roles", value=approval_roles_info, inline=True)
            
            # Installment payment settings
            installment_enabled = server_settings.is_installment_enabled(guild_id)
            embed.add_field(
                name="Installment Payments",
                value="Enabled" if installment_enabled else "Disabled",
                inline=True
            )
            
            if installment_enabled:
                min_percent = server_settings.get_min_installment_percent(guild_id)
                embed.add_field(
                    name="Min Installment %",
                    value=f"{min_percent}%",
                    inline=True
                )
            
            # Add footer with version
            embed.set_footer(text=f"Discord Loan Bot v{config.VERSION}")
            
            # Send the embed
            await send_message(embed=embed)
        except Exception as e:
            logger.error(f"Error viewing settings: {e}")
            
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "There was an error displaying server settings. Please try again.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "There was an error displaying server settings. Please try again.",
                        ephemeral=True
                    )
            except Exception as e2:
                logger.error(f"Error sending error message: {e2}")
                pass

    @app_commands.command(name="set_max_loan", description="Set the maximum loan amount for this server (Admin only)")
    @app_commands.describe(
        amount="The maximum amount that can be borrowed (minimum 1,000)"
    )
    async def set_max_loan(self, interaction: discord.Interaction, amount: int):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You need administrator permissions to use this command.",
                ephemeral=True
            )
        
        # Validate the amount - only enforce a minimum
        if amount < 1000:
            return await interaction.response.send_message(
                "The maximum loan amount must be at least 1,000.",
                ephemeral=True
            )
        
        try:
            # Set the maximum loan amount
            guild_id = str(interaction.guild.id)
            
            server_settings.set_max_loan_amount(guild_id, amount)
            
            # Respond with confirmation
            embed = discord.Embed(
                title="✅ Maximum Loan Amount Set",
                description=f"The maximum loan amount has been set to {amount:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}.",
                color=0x00FF00
            )
            
            embed.add_field(
                name="How it works",
                value=f"Members can now request loans up to {amount:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}.",
                inline=False
            )
            
            embed.add_field(
                name="To change",
                value="Run this command again with a different amount.",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
            
            logger.info(f"Maximum loan amount set to {amount} in guild {interaction.guild.name} (ID: {guild_id})")
            
        except Exception as error:
            logger.error(f"Error setting maximum loan amount: {str(error)}")
            await interaction.response.send_message(
                f"There was an error setting the maximum loan amount: {str(error)}",
                ephemeral=True
            )
            
    @app_commands.command(name="set_max_days", description="Set the maximum repayment period for loans (Admin only)")
    @app_commands.describe(
        days="The maximum number of days allowed for loan repayment (minimum 1 day)",
        unlimited="Set to True to allow unlimited repayment time (ignores days parameter)"
    )
    async def set_max_days(self, interaction: discord.Interaction, days: int, unlimited: bool = False):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You need administrator permissions to use this command.",
                ephemeral=True
            )
        
        # Handle unlimited days option
        if unlimited:
            days = 9999  # Using 9999 days (about 27 years) as effectively unlimited
        
        # Validate the days - only enforce a minimum
        if days < 1:
            return await interaction.response.send_message(
                "The maximum repayment period must be at least 1 day.",
                ephemeral=True
            )
        
        try:
            # Set the maximum repayment days
            guild_id = str(interaction.guild.id)
            
            server_settings.set_max_repayment_days(guild_id, days)
            
            # Respond with confirmation
            embed = discord.Embed(
                title="✅ Maximum Repayment Period Set",
                description=f"The maximum repayment period has been set to {days if days < 9999 else 'unlimited'} days.",
                color=0x00FF00
            )
            
            embed.add_field(
                name="How it works",
                value=f"Members can now request loans with repayment periods up to {days if days < 9999 else 'unlimited'} days.",
                inline=False
            )
            
            embed.add_field(
                name="To change",
                value="Run this command again with a different number of days or use `/set_max_days unlimited:True` for unlimited time.",
                inline=False
            )
            
            # Add current settings info
            max_loan = server_settings.get_max_loan_amount(guild_id)
            embed.add_field(
                name="Current Settings",
                value=f"Max Loan Amount: {max_loan:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}\nMax Repayment Period: {days if days < 9999 else 'Unlimited'} days", 
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
            
            logger.info(f"Maximum repayment days set to {days} in guild {interaction.guild.name} (ID: {guild_id})")
            
        except Exception as error:
            logger.error(f"Error setting maximum repayment days: {str(error)}")
            await interaction.response.send_message(
                f"There was an error setting the maximum repayment period: {str(error)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(SetupCommand(bot)) 