"""
Help command that shows information about all available commands
"""

import discord
from discord import app_commands
from discord.ext import commands
import sys
import os
import config
import logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("discord")

class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="help", description="Get help with the loan bot commands")
    async def help(self, interaction: discord.Interaction):
        try:
            # Check if interaction is already responded to
            if interaction.response.is_done():
                logger.warning("Interaction already acknowledged in help command, using followup instead")
                send_message = interaction.followup.send
            else:
                # Use the normal response
                send_message = interaction.response.send_message
                
            # Create the help embed
            embed = discord.Embed(
                title="📚 Loan Bot Help",
                description="Here are the commands you can use with this bot:",
                color=0x0099FF
            )
            
            # Add loan related commands
            loan_commands = [
                ("/loan <amount> <days>", "Request a loan for your crew"),
                ("/repay <loan_id>", "Repay a loan"),
                ("/pay_installment <loan_id> <amount>", "Make an installment payment on a loan"),
                ("/pending_payments", "View your pending installment payments"),
                ("/myloans", "View your active loans"),
                ("/credit", "Check your credit score")
            ]
            
            command_text = "\n".join([f"**{cmd}** - {desc}" for cmd, desc in loan_commands])
            
            embed.add_field(
                name="⚓ Captain Commands",
                value=command_text,
                inline=False
            )
            
            # Add admin commands if user has admin permissions
            if interaction.user.guild_permissions.administrator:
                admin_commands = [
                    ("/set_captain_role <role>", "Set which role can request loans"),
                    ("/set_max_loan <amount>", "Set the maximum loan amount"),
                    ("/set_max_repayment_days <days>", "Set the maximum repayment period"),
                    ("/set_installment_enabled <true/false>", "Enable/disable installment payments"),
                    ("/set_min_installment_percent <percent>", "Set minimum installment percentage"),
                    ("/setup_loans <channel>", "Configure loan request settings"),
                    ("/allloans", "View all active loans"),
                    ("/view_settings", "View server settings"),
                    ("/loanstats", "View statistics on loans")
                ]
                
                admin_text = "\n".join([f"**{cmd}** - {desc}" for cmd, desc in admin_commands])
                
                embed.add_field(
                    name="🔧 Admin Commands",
                    value=admin_text,
                    inline=False
                )
            
            # Add footer with more information
            embed.set_footer(text="For more detailed help, use the specific command.")
            
            # Send the help message
            await send_message(embed=embed, ephemeral=True)
            
        except Exception as error:
            logger.error(f"Error in help command: {str(error)}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "There was an error showing the help information. Please try again.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "There was an error showing the help information. Please try again.",
                        ephemeral=True
                    )
            except:
                pass


async def setup(bot):
    await bot.add_cog(HelpCommand(bot)) 