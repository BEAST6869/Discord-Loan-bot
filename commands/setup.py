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
    
    @app_commands.command(name="set_captain_role", description="Set which role can request loans (Admin only)")
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
    
    @app_commands.command(name="view_settings", description="View server settings for the loan bot")
    async def view_settings(self, interaction: discord.Interaction):
        try:
            guild_id = str(interaction.guild.id)
            settings = server_settings.get_guild_settings(guild_id)
            
            embed = discord.Embed(
                title="📋 Server Settings",
                description="Current configuration for the Loan Bot in this server",
                color=0x0099FF
            )
            
            # Captain Role
            captain_role_id = settings.get("captain_role_id")
            if captain_role_id:
                captain_role = interaction.guild.get_role(int(captain_role_id))
                captain_value = f"{captain_role.mention} (ID: {captain_role_id})" if captain_role else f"Unknown Role (ID: {captain_role_id})"
            else:
                captain_value = "Not set - All members can request loans"
                
            embed.add_field(
                name="👑 Captain Role",
                value=captain_value,
                inline=False
            )
            
            # Maximum Loan Amount
            max_loan = settings.get("max_loan_amount", 1000000)
            embed.add_field(
                name="💰 Maximum Loan Amount",
                value=f"{max_loan:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
                inline=False
            )
            
            # Maximum Repayment Days
            max_days = settings.get("max_repayment_days", 7)
            embed.add_field(
                name="📅 Maximum Repayment Period",
                value=f"{max_days} days",
                inline=False
            )
            
            # UnbelievaBoat integration
            embed.add_field(
                name="💰 Currency",
                value=f"{config.UNBELIEVABOAT['CURRENCY_NAME']}",
                inline=True
            )
            
            embed.add_field(
                name="🏦 UnbelievaBoat Integration",
                value="✅ Enabled" if config.UNBELIEVABOAT["ENABLED"] else "❌ Disabled",
                inline=True
            )
            
            # Loan settings
            embed.add_field(
                name="💸 Manual Mode",
                value="✅ Enabled" if config.UNBELIEVABOAT["MANUAL_MODE"] else "❌ Disabled",
                inline=True
            )
            
            # Add a footer with instructions
            embed.set_footer(text="Admins can change settings with /set_captain_role, /set_max_loan, and /set_max_days")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as error:
            logger.error(f"Error viewing settings: {str(error)}")
            await interaction.response.send_message(
                f"There was an error viewing server settings: {str(error)}",
                ephemeral=True
            )

    @app_commands.command(name="set_max_loan", description="Set the maximum loan amount for this server (Admin only)")
    @app_commands.describe(
        amount="The maximum amount that can be borrowed (between 10,000 and 10,000,000)"
    )
    async def set_max_loan(self, interaction: discord.Interaction, amount: int):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You need administrator permissions to use this command.",
                ephemeral=True
            )
        
        # Validate the amount
        if amount < 10000 or amount > 10000000:
            return await interaction.response.send_message(
                "The maximum loan amount must be between 10,000 and 10,000,000.",
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
        days="The maximum number of days allowed for loan repayment (between 1 and 30)"
    )
    async def set_max_days(self, interaction: discord.Interaction, days: int):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You need administrator permissions to use this command.",
                ephemeral=True
            )
        
        # Validate the days
        if days < 1 or days > 30:
            return await interaction.response.send_message(
                "The maximum repayment period must be between 1 and 30 days.",
                ephemeral=True
            )
        
        try:
            # Set the maximum repayment days
            guild_id = str(interaction.guild.id)
            
            server_settings.set_max_repayment_days(guild_id, days)
            
            # Respond with confirmation
            embed = discord.Embed(
                title="✅ Maximum Repayment Period Set",
                description=f"The maximum repayment period has been set to {days} days.",
                color=0x00FF00
            )
            
            embed.add_field(
                name="How it works",
                value=f"Members can now request loans with repayment periods up to {days} days.",
                inline=False
            )
            
            embed.add_field(
                name="To change",
                value="Run this command again with a different number of days.",
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