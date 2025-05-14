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

# Initialize logger
logger = logging.getLogger("repay")

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
            guild_id = str(interaction.guild.id)
            
            # Log the repayment attempt
            logger.info(f"Repayment attempt by {interaction.user} (ID: {user_id}) for loan ID: {loan_id} in guild {guild_id}")
            
            # Get loan database from bot
            loan_database = self.bot.loan_database
            
            # Debug log for available loans
            logger.info(f"Current loans in database: {len(loan_database.get('loans', []))}")
            for l in loan_database.get('loans', []):
                logger.info(f"Loan in DB: ID={l.get('id')}, User={l.get('user_id')}, Status={l.get('status')}")
            
            # Find the loan
            if "loans" not in loan_database or not isinstance(loan_database["loans"], list):
                loan_database["loans"] = []
                logger.warning(f"Loans array did not exist in database, initialized empty array")
            
            # Find loan index
            loan_index = -1
            for i, loan in enumerate(loan_database["loans"]):
                if loan and loan.get("id") == loan_id:
                    # First check if this user is the borrower
                    if loan.get("user_id") == user_id:
                        loan_index = i
                        logger.info(f"Loan found: ID={loan_id}, Index={i}, Status={loan.get('status')}")
                        break
                    else:
                        logger.warning(f"User {user_id} attempted to repay loan {loan_id} belonging to user {loan.get('user_id')}")
            
            if loan_index == -1:
                logger.warning(f"Loan not found. ID: {loan_id}, User ID: {user_id}")
                
                # Check if the loan is in the loan_requests array still
                request_found = False
                for req in loan_database.get("loan_requests", []):
                    if req and req.get("id") == loan_id:
                        request_found = True
                        status = req.get("status")
                        logger.warning(f"Found loan in loan_requests with status: {status}")
                        if status == "pending":
                            return await interaction.followup.send(
                                f"Loan #{loan_id} is still pending approval. Please wait for an admin to approve your loan request."
                            )
                        if status == "approved":
                            return await interaction.followup.send(
                                f"Loan #{loan_id} was approved but not properly moved to active loans. Please contact an admin to fix this issue."
                            )
                
                return await interaction.followup.send(
                    f"Loan #{loan_id} not found or you are not the borrower of this loan. Please check the loan ID and try again."
                )
            
            loan = loan_database["loans"][loan_index]
            
            # Check if loan is already repaid
            if loan.get("status") != "active":
                logger.warning(f"Attempted to repay loan #{loan_id} with status: {loan.get('status')}")
                return await interaction.followup.send(
                    f"Loan #{loan_id} cannot be repaid because it is already marked as {loan.get('status', 'unknown')}."
                )
            
            logger.info(f"Processing repayment for loan: {loan}")
            
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
                logger.info(f"Late fee applied: {late_fee}, new total: {loan['total_repayment']}")
            
            # If API integration is enabled, check balance and process payment
            if config.UNBELIEVABOAT["ENABLED"] and unbelievaboat:
                try:
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
                    if user_balance.get("cash", 0) < loan["total_repayment"]:
                        return await interaction.followup.send(
                            f"You don't have enough {config.UNBELIEVABOAT['CURRENCY_NAME']} to repay this loan. "
                            f"You need {loan['total_repayment']} {config.UNBELIEVABOAT['CURRENCY_NAME']} but only have {user_balance.get('cash', 0)}."
                        )
                    
                    logger.info(f"Removing {loan['total_repayment']} from user {user_id} in guild {guild_id}")
                    
                    # Remove the repayment amount from user's balance
                    result = await unbelievaboat.remove_currency(
                        guild_id,
                        user_id,
                        loan["total_repayment"],
                        f"Loan #{loan_id} repayment - {loan['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']} + "
                        f"{loan['interest']} interest{' + ' + str(late_fee) + ' late fee' if late_fee > 0 else ''}"
                    )
                    
                    if not result:
                        logger.error(f"Failed to remove currency from user {user_id} in guild {guild_id}")
                        return await interaction.followup.send(
                            "There was an error processing your repayment with UnbelievaBoat. Please try again or contact an admin."
                        )
                    
                    # Add UnbelievaBoat transaction info to the loan
                    loan["unbelievaboat"] = loan.get("unbelievaboat", {})
                    loan["unbelievaboat"].update({
                        "repayment_processed": True,
                        "balance_after": result.get("cash", 0),
                        "repayment_time": datetime.datetime.now().isoformat()
                    })
                    
                    logger.info(f"Successfully processed repayment, new balance: {result.get('cash', 0)}")
                except Exception as error:
                    logger.error(f"UnbelievaBoat API error: {str(error)}")
                    return await interaction.followup.send(
                        f"There was an error processing your repayment: {str(error)}"
                    )
            
            # Process repayment
            loan["status"] = "repaid"
            loan["repaid_date"] = datetime.datetime.now()
            loan["repaid_by"] = str(interaction.user.id)
            
            # Ensure history array exists
            if "history" not in loan_database:
                loan_database["history"] = []
            
            # Move to history
            loan_database["history"].append(loan.copy())
            loan_database["loans"].pop(loan_index)
            logger.info(f"Loan {loan_id} marked as repaid and moved to history")
            
            # Update credit score
            credit_change = 10 if on_time else -5
            
            if "credit_scores" not in loan_database:
                loan_database["credit_scores"] = {}
            
            if user_id not in loan_database["credit_scores"]:
                loan_database["credit_scores"][user_id] = 100  # Default score
            
            loan_database["credit_scores"][user_id] += credit_change
            logger.info(f"Updated credit score for user {user_id}: {loan_database['credit_scores'][user_id]} (change: {credit_change})")
            
            # Create embed for repayment details
            embed = discord.Embed(
                title="💰 Loan Repaid Successfully!",
                color=0x00FF00
            )
            
            embed.add_field(name="Loan ID", value=f"{loan_id}", inline=True)
            embed.add_field(name="Loan Amount", value=f"{loan['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
            embed.add_field(name="Interest Paid", value=f"{loan['interest']} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
            
            total_field = f"{loan['total_repayment']} {config.UNBELIEVABOAT['CURRENCY_NAME']}"
            if late_fee > 0:
                total_field += f" (including {late_fee} late fee)"
            embed.add_field(name="Total Paid", value=total_field, inline=True)
            
            status_text = "✅ Paid on time" if on_time else f"⚠️ Paid late ({late_fee} {config.UNBELIEVABOAT['CURRENCY_NAME']} fee applied)"
            embed.add_field(name="Status", value=status_text, inline=True)
            
            credit_sign = "+" if credit_change > 0 else ""
            embed.add_field(name="Credit Score Change", value=f"{credit_sign}{credit_change}", inline=True)
            embed.add_field(name="New Credit Score", value=f"{loan_database['credit_scores'][user_id]}", inline=True)
            
            # For API integration, add info about currency deduction
            if config.UNBELIEVABOAT["ENABLED"] and loan.get("unbelievaboat", {}).get("repayment_processed"):
                embed.add_field(
                    name="Currency Deducted",
                    value=f"✅ {loan['total_repayment']} {config.UNBELIEVABOAT['CURRENCY_NAME']} deducted from your balance",
                    inline=False
                )
                embed.add_field(
                    name="Remaining Balance",
                    value=f"{loan['unbelievaboat'].get('balance_after', 'Unknown')} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
                    inline=True
                )
            
            # Send response
            await interaction.followup.send(embed=embed)
            
            logger.info(f"Loan #{loan_id} successfully repaid by {interaction.user}")
            
        except Exception as error:
            logger.error(f"Error in repayment: {str(error)}")
            import traceback
            logger.error(traceback.format_exc())
            
            try:
                await interaction.followup.send(
                    f"An error occurred while processing your repayment: {str(error)}"
                )
            except:
                logger.error("Failed to send error message")

    # Button handler for repayment
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.type == discord.InteractionType.component:
            return
            
        if not interaction.data["custom_id"].startswith("repay_"):
            return
            
        logger.info(f"Received repay button interaction with custom_id: {interaction.data['custom_id']}")
        
        # Parse the custom ID
        try:
            parts = interaction.data["custom_id"].split("_")
            if len(parts) < 3:
                logger.error(f"Invalid custom_id format: {interaction.data['custom_id']}")
                return await interaction.response.send_message(
                    "Invalid repayment button. Please use the /repay command instead.",
                    ephemeral=True
                )
                
            user_id = parts[1]
            loan_id = parts[2]
            
            logger.info(f"Parsed button interaction: user_id={user_id}, loan_id={loan_id}")
            
            # Verify the user is the loan owner
            if str(interaction.user.id) != user_id:
                logger.warning(f"User {interaction.user.id} attempted to repay loan {loan_id} belonging to user {user_id}")
                return await interaction.response.send_message(
                    "You can only repay your own loans!",
                    ephemeral=True
                )
            
            # Process the repayment
            await interaction.response.defer(ephemeral=True)
            
            # Create a fake options object for compatibility
            class FakeOptions:
                def __init__(self, loan_id):
                    self.loan_id = loan_id
                    
                def get_string(self, name):
                    if name == "loan_id":
                        return self.loan_id
                    return None
                    
            fake_options = FakeOptions(loan_id)
            
            # Call the repay command directly
            await self.repay(interaction, loan_id)
            
        except Exception as e:
            logger.error(f"Error processing repay button: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            try:
                await interaction.followup.send(
                    f"An error occurred while processing your repayment: {str(e)}",
                    ephemeral=True
                )
            except:
                logger.error("Failed to send error message after button interaction")


async def setup(bot):
    await bot.add_cog(RepayCommand(bot)) 