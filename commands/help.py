"""
Help command that shows information about all available commands
"""

import discord
from discord import app_commands
from discord.ext import commands
import sys
import os
import config

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="help", description="Show information about all available commands")
    async def help(self, interaction: discord.Interaction):
        """Show help information about all available commands"""
        
        # Create base embed
        embed = discord.Embed(
            title="📚 Loan Bot Help",
            description=f"Here are all the available commands for the Discord Loan Bot",
            color=0x4A90E2
        )
        
        # Loan Commands
        embed.add_field(
            name="💰 Loan Commands",
            value=(
                f"`/loan <amount> <days>` - Request a loan for your crew\n"
                f"`/repay <loan_id>` - Repay an active loan\n"
                f"`/myloans` - View your active loans\n"
                f"`/allloans` - View all active loans in the server (Admin only)\n"
                f"`/loanstats` - View loan statistics for the server"
            ),
            inline=False
        )
        
        # Loan Request Commands
        embed.add_field(
            name="📝 Loan Request Commands",
            value=(
                f"`/loanrequests` - View pending loan requests (Admin/Approval Roles)\n"
                f"`/approveloan <loan_id>` - Approve a pending loan request (Admin/Approval Roles)\n"
                f"`/denyloan <loan_id> <reason>` - Deny a pending loan request (Admin/Approval Roles)"
            ),
            inline=False
        )
        
        # Credit Commands
        embed.add_field(
            name="💳 Credit Commands",
            value=(
                f"`/credit <user>` - Check credit score for a user\n"
                f"`/adjustcredit <user> <amount>` - Adjust credit score (Admin only)"
            ),
            inline=False
        )
        
        # Admin Commands
        embed.add_field(
            name="⚙️ Admin Setup Commands",
            value=(
                f"`/set_captain_role <role>` - Set which role can request loans (Admin only)\n"
                f"`/set_max_loan <amount>` - Set the maximum loan amount (Admin only)\n"
                f"`/setup_loans <channel>` - Configure loan request channel and approval roles (Admin only)\n"
                f"`/set_admin_channel <channel>` - Set where loan notifications appear (Admin only)\n"
                f"`/loan_notification_roles <roles>` - Set roles to ping for loan requests (Admin only)\n"
                f"`/view_loan_settings` - View loan request configuration (Admin only)\n"
                f"`/view_settings` - View server settings for the loan bot"
            ),
            inline=False
        )
        
        # General Commands
        embed.add_field(
            name="ℹ️ General Commands",
            value=(
                f"`/help` - Shows this help message"
            ),
            inline=False
        )
        
        # Currency Info
        embed.add_field(
            name="🪙 Currency Information",
            value=(
                f"This bot uses {config.UNBELIEVABOAT['CURRENCY_NAME']} as currency\n"
                f"UnbelievaBoat Integration: {'✅ Enabled' if config.UNBELIEVABOAT['ENABLED'] else '❌ Disabled'}"
            ),
            inline=False
        )
        
        # Captain Role Info
        import server_settings
        guild_id = str(interaction.guild.id)
        captain_role_id = server_settings.get_captain_role(guild_id)
        
        if captain_role_id:
            captain_role = interaction.guild.get_role(int(captain_role_id))
            captain_info = f"Only members with the {captain_role.mention} role can request loans"
        else:
            captain_info = "Any member can request loans"
        
        embed.add_field(
            name="👑 Captain Role",
            value=captain_info,
            inline=False
        )
        
        # Approval Roles Info
        approval_roles = server_settings.get_approval_roles(guild_id)
        admin_channel_id = server_settings.get_admin_channel(guild_id)
        
        approval_info = "**Loan Request System**\n"
        
        if admin_channel_id:
            admin_channel = interaction.guild.get_channel(int(admin_channel_id))
            approval_info += f"Loan requests are sent to: {admin_channel.mention if admin_channel else 'Unknown channel'}\n"
        else:
            approval_info += "Loan request channel: Not configured\n"
        
        if approval_roles:
            role_mentions = []
            for role_id in approval_roles:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    role_mentions.append(role.mention)
            
            if role_mentions:
                approval_info += f"Approval roles: {', '.join(role_mentions)}"
            else:
                approval_info += "Approval roles: Configured but roles not found"
        else:
            approval_info += "Approval roles: Not configured (Admin only)"
        
        embed.add_field(
            name="✅ Loan Approval",
            value=approval_info,
            inline=False
        )
        
        # Add footer with support info
        embed.set_footer(text="For support, contact a server admin")
        
        # Send the help embed
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(HelpCommand(bot)) 