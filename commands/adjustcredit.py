import discord
from discord import app_commands
from discord.ext import commands
import config
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AdjustCreditCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="adjustcredit", description="Adjust a user's credit score (Admin only)")
    @app_commands.describe(
        user="The user to adjust credit score for",
        amount="The amount to adjust (positive or negative)",
        reason="Reason for the adjustment"
    )
    async def adjustcredit(self, interaction: discord.Interaction, user: discord.User, amount: int, reason: str):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You need Administrator permissions to use this command.",
                ephemeral=True
            )
        
        await interaction.response.defer()
        
        # Get loan database from bot
        loan_database = self.bot.loan_database
        
        # Ensure credit scores dictionary exists
        if "credit_scores" not in loan_database:
            loan_database["credit_scores"] = {}
        
        user_id = str(user.id)
        
        # Get current credit score or default to 100
        current_score = loan_database["credit_scores"].get(user_id, 100)
        
        # Apply adjustment
        new_score = current_score + amount
        
        # Update credit score
        loan_database["credit_scores"][user_id] = new_score
        
        # Create a log entry
        if "credit_adjustments" not in loan_database:
            loan_database["credit_adjustments"] = []
            
        adjustment = {
            "user_id": user_id,
            "admin_id": str(interaction.user.id),
            "previous_score": current_score,
            "new_score": new_score,
            "amount": amount,
            "reason": reason,
            "timestamp": discord.utils.utcnow().isoformat()
        }
        
        loan_database["credit_adjustments"].append(adjustment)
        
        # Create embed for response
        embed = discord.Embed(
            title="📊 Credit Score Adjusted",
            description=f"Credit score for {user.mention} has been adjusted.",
            color=0x00AA00 if amount >= 0 else 0xAA0000
        )
        
        embed.add_field(
            name="Previous Score",
            value=str(current_score),
            inline=True
        )
        
        embed.add_field(
            name="Adjustment",
            value=f"{'+' if amount >= 0 else ''}{amount}",
            inline=True
        )
        
        embed.add_field(
            name="New Score",
            value=str(new_score),
            inline=True
        )
        
        embed.add_field(
            name="Reason",
            value=reason,
            inline=False
        )
        
        # Add admin as footer
        embed.set_footer(text=f"Adjusted by {interaction.user}")
        
        # Add user avatar as thumbnail
        embed.set_thumbnail(url=user.display_avatar.url)
        
        # Send public response
        await interaction.followup.send(embed=embed)
        
        # Try to notify the user via DM
        try:
            user_embed = discord.Embed(
                title="📊 Your Credit Score Was Adjusted",
                description=f"Your credit score has been adjusted by an administrator.",
                color=0x00AA00 if amount >= 0 else 0xAA0000
            )
            
            user_embed.add_field(
                name="Previous Score",
                value=str(current_score),
                inline=True
            )
            
            user_embed.add_field(
                name="Adjustment",
                value=f"{'+' if amount >= 0 else ''}{amount}",
                inline=True
            )
            
            user_embed.add_field(
                name="New Score",
                value=str(new_score),
                inline=True
            )
            
            user_embed.add_field(
                name="Reason",
                value=reason,
                inline=False
            )
            
            user_embed.set_footer(text=f"Adjusted by {interaction.user}")
            
            await user.send(embed=user_embed)
        except:
            # If we can't DM the user, just log it and continue
            print(f"Could not DM user {user.id} about credit score adjustment.")


async def setup(bot):
    await bot.add_cog(AdjustCreditCommand(bot)) 