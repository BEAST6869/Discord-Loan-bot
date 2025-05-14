import discord
from discord import app_commands
from discord.ext import commands
import datetime
import config
import sys
import os
import logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize UnbelievaBoat integration
unbelievaboat = None

# Try to get port configuration from environment
unbelievaboat_port = None
try:
    port_env = os.environ.get('UNBELIEVABOAT_PORT')
    if port_env:
        unbelievaboat_port = int(port_env)
        logging.info(f"Using UnbelievaBoat port from environment: {unbelievaboat_port}")
except (ValueError, TypeError) as e:
    logging.warning(f"Invalid UNBELIEVABOAT_PORT environment variable: {e}")

if config.UNBELIEVABOAT["ENABLED"]:
    from unbelievaboat_integration import UnbelievaBoatAPI
    unbelievaboat = UnbelievaBoatAPI(
        api_key=config.UNBELIEVABOAT["API_KEY"],
        port=unbelievaboat_port,
        timeout=45  # Increased timeout for Render
    )
    logging.info("UnbelievaBoat API integration enabled")
else:
    logging.info("UnbelievaBoat API integration disabled")

# Always import manual integration as fallback
import manual_unbelievaboat as manual_integration


class RepayCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="repay", description="Repay a loan")
    @app_commands.describe(
        loan_id="The ID of the loan to repay (4-digit number)"
    )
    async def repay(self, interaction: discord.Interaction, loan_id: str):
        try:
            # Defer the reply first to prevent interaction timeout
            await interaction.response.defer()
            
            if not loan_id:
                return await interaction.followup.send(
                    "Please provide a valid loan ID."
                )
            
            user_id = str(interaction.user.id)
            
            # Log the repayment attempt
            print(f"Repayment attempt by {interaction.user} for loan ID: {loan_id}")
            
            # Get loan database from bot
            loan_database = self.bot.loan_database
            
            # Find the loan
            if "loans" not in loan_database or not isinstance(loan_database["loans"], list):
                loan_database["loans"] = []
            
            # Find loan index
            loan_index = -1
            for i, loan in enumerate(loan_database["loans"]):
                if loan and loan.get("id") == loan_id and loan.get("user_id") == user_id:
                    loan_index = i
                    break
            
            if loan_index == -1:
                print(f"Loan not found. ID: {loan_id}, User ID: {user_id}")
                print(f"Available loans: {loan_database['loans']}")
                
                return await interaction.followup.send(
                    f"Loan #{loan_id} not found or you are not the borrower of this loan. Please check the loan ID and try again."
                )
            
            loan = loan_database["loans"][loan_index]
            print(f"Loan found: {loan}")
            
            # Check if repayment is late and calculate late fee if applicable
            current_date = datetime.datetime.now()
            due_date = loan["due_date"]
            on_time = current_date <= due_date
            late_fee = 0
            
            if not on_time:
                # Apply 5% late fee
                late_fee = round(loan["amount"] * 0.05)
                loan["late_fee"] = late_fee
                loan["total_repayment"] += late_fee
            
            # If API integration is enabled, check balance and process payment
            if config.UNBELIEVABOAT["ENABLED"] and unbelievaboat:
                try:
                    # Use the current guild's ID instead of the config's fixed guild ID
                    guild_id = str(interaction.guild.id)
                    user_id = str(interaction.user.id)
                    
                    logger.info(f"Checking balance for user {user_id} in guild {guild_id}")
                    
                    # Get user's current balance
                    user_balance = await unbelievaboat.get_user_balance(guild_id, user_id)
                    
                    if not user_balance:
                        logger.error(f"Unable to retrieve balance for user {user_id} in guild {guild_id}")
                        return await interaction.followup.send(
                            "Unable to check your balance with UnbelievaBoat. Please try again or contact an admin."
                        )
                    
                    logger.info(f"User balance: {user_balance.get('cash', 0)}, Required: {loan['total_repayment']}")
                    
                    # Check if user has enough currency
                    if user_balance["cash"] < loan["total_repayment"]:
                        return await interaction.followup.send(
                            f"You don't have enough {config.UNBELIEVABOAT['CURRENCY_NAME']} to repay this loan. "
                            f"You need {loan['total_repayment']} {config.UNBELIEVABOAT['CURRENCY_NAME']} but only have {user_balance['cash']}."
                        )
                    
                    logger.info(f"Removing {loan['total_repayment']} from user {user_id} in guild {guild_id}")
                    
                    # Remove the repayment amount from user's balance
                    result = await unbelievaboat.remove_currency(
                        guild_id,
                        user_id,
                        loan["total_repayment"],
                        f"Loan #{loan_id} repayment - {loan['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']} + "
                        f"{loan['interest']} interest{' + ' + str(late_fee) + ' late fee' if not on_time else ''}"
                    )
                    
                    if not result:
                        logger.error(f"Failed to remove currency from user {user_id} in guild {guild_id}")
                        return await interaction.followup.send(
                            "There was an error processing your repayment with UnbelievaBoat. Please try again or contact an admin."
                        )
                    
                    # Add UnbelievaBoat transaction info to the loan
                    loan["unbelievaboat"] = {
                        "repayment_processed": True,
                        "balance_after": result["cash"]
                    }
                    
                    logger.info(f"Successfully processed repayment, new balance: {result['cash']}")
                except Exception as error:
                    logger.error(f"UnbelievaBoat API error: {str(error)}")
                    return await interaction.followup.send(
                        f"There was an error processing your repayment: {str(error)}"
                    )
            
            # Process repayment
            loan["status"] = "repaid"
            loan["repaid_date"] = datetime.datetime.now()
            
            # Ensure history array exists
            if "history" not in loan_database:
                loan_database["history"] = []
            
            # Move to history
            loan_database["history"].append(loan.copy())
            loan_database["loans"].pop(loan_index)
            
            # Update credit score
            credit_change = 10 if on_time else -5
            
            if "credit_scores" not in loan_database:
                loan_database["credit_scores"] = {}
            
            if user_id not in loan_database["credit_scores"]:
                loan_database["credit_scores"][user_id] = 100  # Default score
            
            loan_database["credit_scores"][user_id] += credit_change
            
            # Create embed for repayment details
            embed = discord.Embed(
                title="💰 Loan Repaid Successfully!",
                color=0x00FF00
            )
            
            embed.add_field(name="Loan ID", value=f"{loan_id}", inline=True)
            embed.add_field(name="Loan Amount", value=f"{loan['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
            embed.add_field(name="Interest Paid", value=f"{loan['interest']} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
            embed.add_field(name="Total Paid", value=f"{loan['total_repayment']} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
            
            status_text = "✅ Paid on time" if on_time else f"⚠️ Paid late ({late_fee} {config.UNBELIEVABOAT['CURRENCY_NAME']} fee applied)"
            embed.add_field(name="Status", value=status_text, inline=True)
            
            credit_sign = "+" if credit_change > 0 else ""
            embed.add_field(name="Credit Score Change", value=f"{credit_sign}{credit_change}", inline=True)
            embed.add_field(name="New Credit Score", value=f"{loan_database['credit_scores'][user_id]}", inline=True)
            
            # For API integration, add info about currency deduction
            if config.UNBELIEVABOAT["ENABLED"] and loan.get("unbelievaboat"):
                embed.add_field(
                    name="Currency Deducted",
                    value=f"✅ {loan['total_repayment']} {config.UNBELIEVABOAT['CURRENCY_NAME']} deducted from your balance",
                    inline=False
                )
                embed.add_field(
                    name="Remaining Balance",
                    value=f"{loan['unbelievaboat']['balance_after']} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
                    inline=True
                )
            
            # Send response
            await interaction.followup.send(embed=embed)
            
            print(f"Loan #{loan_id} successfully repaid by {interaction.user}")
            
        except Exception as error:
            print(f"Error in repayment: {str(error)}")
            
            try:
                await interaction.followup.send(
                    "An error occurred while processing your repayment. Please try again later."
                )
            except:
                print("Failed to send error message")

    # Button handler for repayment
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.type == discord.InteractionType.component:
            return
            
        if not interaction.data["custom_id"].startswith("repay_"):
            return
            
        # Parse the custom ID
        parts = interaction.data["custom_id"].split("_")
        user_id = parts[1]
        loan_id = parts[2]
        
        # Verify the user is the loan owner
        if str(interaction.user.id) != user_id:
            return await interaction.response.send_message(
                "You can only repay your own loans!",
                ephemeral=True
            )
        
        # Process the repayment
        await interaction.response.defer(ephemeral=True)
        
        # Create a fake options object for the command
        class FakeOptions:
            def __init__(self, loan_id):
                self.loan_id = loan_id
                
            def get_string(self, name):
                if name == "loan_id":
                    return self.loan_id
                return None
        
        # Manually set up options on the interaction object
        interaction.options = FakeOptions(loan_id)
        
        # Call the repay command with modified interaction
        await self.repay(interaction, loan_id)


async def setup(bot):
    await bot.add_cog(RepayCommand(bot)) 