import discord
from discord import app_commands
from discord.ext import commands
import datetime
import config
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AllLoansCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="allloans", description="View all active loans (Admin only)")
    async def allloans(self, interaction: discord.Interaction):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You need Administrator permissions to use this command.",
                ephemeral=True
            )
        
        await interaction.response.defer()
        
        # Get loan database from bot
        loan_database = self.bot.loan_database
        
        # Get all active loans
        if "loans" not in loan_database:
            loan_database["loans"] = []
            
        active_loans = loan_database["loans"]
        
        if not active_loans:
            return await interaction.followup.send(
                "There are no active loans at the moment.",
                ephemeral=True
            )
        
        # Sort loans by due date (oldest first)
        active_loans.sort(key=lambda loan: loan.get("due_date", datetime.datetime.max))
        
        # Calculate totals
        total_loans = len(active_loans)
        total_amount = sum(loan.get("amount", 0) for loan in active_loans)
        total_repayment = sum(loan.get("total_repayment", 0) for loan in active_loans)
        
        # Create embed
        embed = discord.Embed(
            title="🏦 All Active Loans",
            description=f"There are {total_loans} active loan(s) totaling {total_amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}.",
            color=0x0099FF
        )
        
        # Group loans by user for cleaner display
        loans_by_user = {}
        
        for loan in active_loans:
            user_id = loan.get("user_id", "unknown")
            if user_id not in loans_by_user:
                loans_by_user[user_id] = []
            loans_by_user[user_id].append(loan)
        
        # Add fields for each user's loans
        for user_id, user_loans in loans_by_user.items():
            try:
                user = await self.bot.fetch_user(int(user_id))
                user_name = f"{user.name} ({user.id})"
            except:
                user_name = f"Unknown User ({user_id})"
            
            # Create loan details string
            loan_details = []
            
            for loan in user_loans:
                loan_id = loan.get("id", "????")
                amount = loan.get("amount", 0)
                total_to_repay = loan.get("total_repayment", 0)
                due_date = loan.get("due_date")
                
                if due_date:
                    # Calculate if loan is overdue
                    is_overdue = datetime.datetime.now() > due_date
                    status = "⚠️ OVERDUE" if is_overdue else "✅ Active"
                    
                    # Calculate days remaining
                    days_remaining = (due_date - datetime.datetime.now()).days
                    days_text = f"{days_remaining} days remaining" if days_remaining > 0 else "Due today!" if days_remaining == 0 else f"{abs(days_remaining)} days overdue"
                    
                    # Format due date
                    due_timestamp = int(due_date.timestamp())
                    due_date_text = f"<t:{due_timestamp}:F> ({days_text})"
                else:
                    status = "⚠️ Unknown due date"
                    due_date_text = "Unknown"
                
                loan_details.append(
                    f"**Loan #{loan_id}**\n"
                    f"Amount: {amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                    f"Repayment: {total_to_repay} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                    f"Due: {due_date_text}\n"
                    f"Status: {status}"
                )
            
            # Combine all loans for this user
            field_value = "\n\n".join(loan_details)
            if len(field_value) > 1024:  # Discord embed field value limit
                field_value = field_value[:1000] + "...\n(More loans not shown)"
            
            embed.add_field(
                name=user_name,
                value=field_value,
                inline=False
            )
        
        # Add summary to the embed footer
        embed.set_footer(text=f"Total outstanding: {total_repayment} {config.UNBELIEVABOAT['CURRENCY_NAME']} | Run /loanstats for more detailed statistics")
        
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AllLoansCommand(bot)) 