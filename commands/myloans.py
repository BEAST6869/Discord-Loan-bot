import discord
from discord import app_commands
from discord.ext import commands
import datetime
import config
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MyLoansCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="myloans", description="View your current loans")
    async def myloans(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        user_id = str(interaction.user.id)
        
        # Get loan database from bot
        loan_database = self.bot.loan_database
        
        # Get all loans for the user
        if "loans" not in loan_database:
            loan_database["loans"] = []
            
        active_loans = [loan for loan in loan_database["loans"] 
                         if loan.get("user_id") == user_id and loan.get("status") == "active"]
        
        if not active_loans:
            return await interaction.followup.send(
                "You don't have any active loans.",
                ephemeral=True
            )
        
        # Create embed
        embed = discord.Embed(
            title="🏦 Your Active Loans",
            description=f"You have {len(active_loans)} active loan(s).",
            color=0x0099FF
        )
        
        # Calculate totals
        total_borrowed = sum(loan["amount"] for loan in active_loans)
        total_repayment = sum(loan["total_repayment"] for loan in active_loans)
        
        # Add loan details for each loan
        for i, loan in enumerate(active_loans):
            loan_id = loan["id"]
            amount = loan["amount"]
            total_to_repay = loan["total_repayment"]
            due_date = loan["due_date"]
            request_date = loan["request_date"]
            
            # Calculate if loan is overdue
            is_overdue = datetime.datetime.now() > due_date
            status = "⚠️ OVERDUE" if is_overdue else "✅ Active"
            
            # Calculate days remaining
            days_remaining = (due_date - datetime.datetime.now()).days
            days_text = f"{days_remaining} days remaining" if days_remaining > 0 else "Due today!" if days_remaining == 0 else f"{abs(days_remaining)} days overdue"
            
            # Format timestamps
            due_timestamp = int(due_date.timestamp())
            request_timestamp = int(request_date.timestamp())
            
            field_value = (
                f"**Amount:** {amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                f"**Repayment:** {total_to_repay} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                f"**Borrowed:** <t:{request_timestamp}:R>\n"
                f"**Due:** <t:{due_timestamp}:F> ({days_text})\n"
                f"**Status:** {status}\n"
                f"Use `/repay {loan_id}` to repay this loan."
            )
            
            embed.add_field(
                name=f"Loan #{loan_id}",
                value=field_value,
                inline=False
            )
        
        # Add summary to the embed footer
        embed.set_footer(text=f"Total borrowed: {total_borrowed} {config.UNBELIEVABOAT['CURRENCY_NAME']} | Total to repay: {total_repayment} {config.UNBELIEVABOAT['CURRENCY_NAME']}")
        
        # Create buttons for each loan
        view = discord.ui.View()
        
        # Add repay buttons for each loan
        for loan in active_loans:
            button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=f"Repay Loan #{loan['id']}",
                custom_id=f"repay_{user_id}_{loan['id']}"
            )
            view.add_item(button)
        
        await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(MyLoansCommand(bot)) 