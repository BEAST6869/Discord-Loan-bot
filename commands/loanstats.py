import discord
from discord import app_commands
from discord.ext import commands
import datetime
import config
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class LoanStatsCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="loanstats", description="View loan statistics for yourself or the server")
    @app_commands.describe(
        user="The user to view stats for (leave empty for server stats)"
    )
    async def loanstats(self, interaction: discord.Interaction, user: discord.User = None):
        await interaction.response.defer()
        
        # Get loan database from bot
        loan_database = self.bot.loan_database
        
        # Make sure collections exist
        if "loans" not in loan_database:
            loan_database["loans"] = []
        if "history" not in loan_database:
            loan_database["history"] = []
        if "credit_scores" not in loan_database:
            loan_database["credit_scores"] = {}
        
        # If a user is specified, show personal stats
        if user:
            await self._show_user_stats(interaction, user)
        else:
            await self._show_server_stats(interaction)
    
    async def _show_user_stats(self, interaction, user):
        user_id = str(user.id)
        loan_database = self.bot.loan_database
        
        # Get all loans for the user
        active_loans = [loan for loan in loan_database["loans"] 
                        if loan.get("user_id") == user_id and loan.get("status") == "active"]
        
        # Get loan history for the user
        completed_loans = [loan for loan in loan_database["history"] 
                           if loan.get("user_id") == user_id and loan.get("status") == "repaid"]
        
        # Get credit score
        credit_score = loan_database["credit_scores"].get(user_id, 100)  # Default score is 100
        
        # Calculate statistics
        total_borrowed = sum(loan["amount"] for loan in completed_loans + active_loans)
        total_repaid = sum(loan["total_repayment"] for loan in completed_loans)
        total_interest_paid = sum(loan.get("interest", 0) for loan in completed_loans)
        total_late_fees = sum(loan.get("late_fee", 0) for loan in completed_loans)
        current_debt = sum(loan["total_repayment"] for loan in active_loans)
        
        # Calculate on-time vs late payments
        on_time_payments = sum(1 for loan in completed_loans 
                              if loan.get("repaid_date") and loan.get("due_date") 
                              and loan["repaid_date"] <= loan["due_date"])
        
        late_payments = len(completed_loans) - on_time_payments
        
        # Create embed
        embed = discord.Embed(
            title=f"📊 Loan Statistics for {user.display_name}",
            color=0x00AAFF
        )
        
        # Current loans
        embed.add_field(
            name="Current Loans",
            value=f"Active Loans: {len(active_loans)}\nCurrent Debt: {current_debt} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
            inline=False
        )
        
        # Loan history
        embed.add_field(
            name="Loan History",
            value=f"Total Loans Taken: {len(completed_loans) + len(active_loans)}\n"
                  f"Loans Repaid: {len(completed_loans)}\n"
                  f"Total Borrowed: {total_borrowed} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                  f"Total Repaid: {total_repaid} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
            inline=False
        )
        
        # Payment history
        embed.add_field(
            name="Payment History",
            value=f"On-time Payments: {on_time_payments}\n"
                  f"Late Payments: {late_payments}\n"
                  f"Interest Paid: {total_interest_paid} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                  f"Late Fees Paid: {total_late_fees} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
            inline=False
        )
        
        # Credit information
        credit_rating = "Excellent" if credit_score >= 120 else \
                        "Good" if credit_score >= 100 else \
                        "Fair" if credit_score >= 80 else \
                        "Poor" if credit_score >= 60 else "Very Poor"
        
        embed.add_field(
            name="Credit Information",
            value=f"Credit Score: {credit_score}\n"
                  f"Rating: {credit_rating}",
            inline=False
        )
        
        # Set footer
        embed.set_footer(text="Higher credit score = better loan terms")
        
        # Add user avatar as thumbnail
        embed.set_thumbnail(url=user.display_avatar.url)
        
        await interaction.followup.send(embed=embed)
    
    async def _show_server_stats(self, interaction):
        loan_database = self.bot.loan_database
        
        # Total loans data
        active_loans = loan_database["loans"]
        completed_loans = loan_database["history"]
        
        # Calculate stats
        total_loans_ever = len(active_loans) + len(completed_loans)
        total_active_loans = len(active_loans)
        total_completed_loans = len(completed_loans)
        
        total_borrowed_ever = sum(loan.get("amount", 0) for loan in active_loans + completed_loans)
        total_active_debt = sum(loan.get("total_repayment", 0) for loan in active_loans)
        total_repaid = sum(loan.get("total_repayment", 0) for loan in completed_loans)
        
        total_interest_paid = sum(loan.get("interest", 0) for loan in completed_loans)
        total_late_fees = sum(loan.get("late_fee", 0) for loan in completed_loans)
        
        # Get number of unique borrowers
        unique_borrowers_active = len(set(loan.get("user_id") for loan in active_loans if loan.get("user_id")))
        unique_borrowers_ever = len(set(loan.get("user_id") for loan in active_loans + completed_loans if loan.get("user_id")))
        
        # On-time vs late payments
        on_time_payments = sum(1 for loan in completed_loans 
                              if loan.get("repaid_date") and loan.get("due_date") 
                              and loan["repaid_date"] <= loan["due_date"])
        
        late_payments = total_completed_loans - on_time_payments
        
        # Create embed
        embed = discord.Embed(
            title=f"📈 Server Loan Statistics",
            description="Overall statistics for all loans in this server",
            color=0x00AAFF
        )
        
        # Loan summary
        embed.add_field(
            name="Loan Summary",
            value=f"Total Loans Ever: {total_loans_ever}\n"
                  f"Active Loans: {total_active_loans}\n"
                  f"Completed Loans: {total_completed_loans}\n"
                  f"Unique Borrowers: {unique_borrowers_ever} (Active: {unique_borrowers_active})",
            inline=False
        )
        
        # Financial summary
        embed.add_field(
            name="Financial Summary",
            value=f"Total Borrowed Ever: {total_borrowed_ever} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                  f"Current Outstanding Debt: {total_active_debt} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                  f"Total Repaid: {total_repaid} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                  f"Interest Collected: {total_interest_paid} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                  f"Late Fees Collected: {total_late_fees} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
            inline=False
        )
        
        # Payment statistics
        on_time_percentage = 0 if total_completed_loans == 0 else (on_time_payments / total_completed_loans) * 100
        
        embed.add_field(
            name="Payment Statistics",
            value=f"On-time Payments: {on_time_payments} ({on_time_percentage:.1f}%)\n"
                  f"Late Payments: {late_payments} ({100 - on_time_percentage:.1f}%)",
            inline=False
        )
        
        # Top borrowers - future enhancement
        
        # Current time as footer
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        embed.set_footer(text=f"Stats as of {current_time}")
        
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(LoanStatsCommand(bot)) 