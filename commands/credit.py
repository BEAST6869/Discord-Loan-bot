import discord
from discord import app_commands
from discord.ext import commands
import config
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class CreditCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="credit", description="Check your credit score and loan history")
    async def credit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        user_id = str(interaction.user.id)
        
        # Get loan database from bot
        loan_database = self.bot.loan_database
        
        # Ensure credit scores dictionary exists
        if "credit_scores" not in loan_database:
            loan_database["credit_scores"] = {}
        
        # Get credit score or default to 100
        credit_score = loan_database["credit_scores"].get(user_id, 100)
        
        # Get completed loans
        if "history" not in loan_database:
            loan_database["history"] = []
            
        completed_loans = [loan for loan in loan_database["history"] 
                          if loan.get("user_id") == user_id and loan.get("status") == "repaid"]
        
        # Get active loans
        if "loans" not in loan_database:
            loan_database["loans"] = []
            
        active_loans = [loan for loan in loan_database["loans"] 
                        if loan.get("user_id") == user_id and loan.get("status") == "active"]
        
        # Calculate statistics
        total_loans = len(completed_loans) + len(active_loans)
        on_time_payments = sum(1 for loan in completed_loans 
                              if loan.get("repaid_date") and loan.get("due_date") 
                              and loan["repaid_date"] <= loan["due_date"])
        
        late_payments = len(completed_loans) - on_time_payments
        
        # Calculate repayment rate
        repayment_rate = 0 if total_loans == 0 else (len(completed_loans) / total_loans) * 100
        
        # Determine credit rating and interest rate
        if credit_score >= 150:
            credit_rating = "Excellent"
            interest_rate = 5
        elif credit_score >= 100:
            credit_rating = "Good"
            interest_rate = 10
        elif credit_score >= 50:
            credit_rating = "Fair"
            interest_rate = 15
        else:
            credit_rating = "Poor"
            interest_rate = 20
        
        # Create embed
        embed = discord.Embed(
            title="💳 Credit Report",
            color=0x00AAFF
        )
        
        # Credit score section
        embed.add_field(
            name="Credit Score",
            value=f"**{credit_score}** - {credit_rating}",
            inline=False
        )
        
        # Credit history
        embed.add_field(
            name="Loan History",
            value=f"Total Loans: {total_loans}\n"
                  f"Active Loans: {len(active_loans)}\n"
                  f"Repaid Loans: {len(completed_loans)}\n"
                  f"Repayment Rate: {repayment_rate:.1f}%",
            inline=True
        )
        
        # Payment history
        embed.add_field(
            name="Payment History",
            value=f"On-time Payments: {on_time_payments}\n"
                  f"Late Payments: {late_payments}",
            inline=True
        )
        
        # Interest rate section
        embed.add_field(
            name="Interest Rate",
            value=f"Your current interest rate is **{interest_rate}%**",
            inline=False
        )
        
        # Credit improvement tips
        tips = []
        if late_payments > 0:
            tips.append("• Make payments on time to avoid late fees")
        if credit_score < 100:
            tips.append("• Pay back several loans on time to improve your score")
        if len(active_loans) > 3:
            tips.append("• Reduce your number of active loans")
        
        if tips:
            embed.add_field(
                name="Tips to Improve Your Credit",
                value="\n".join(tips),
                inline=False
            )
        
        # Set footer
        embed.set_footer(text="Credit scores update with each loan repayment")
        
        # Add user avatar as thumbnail
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(CreditCommand(bot)) 