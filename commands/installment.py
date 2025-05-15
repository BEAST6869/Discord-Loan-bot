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
logger = logging.getLogger("installment")

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


class InstallmentCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    def _parse_datetime(self, dt_value):
        """Helper to parse datetime values from database that might be strings"""
        if isinstance(dt_value, datetime.datetime):
            return dt_value
        elif isinstance(dt_value, str):
            try:
                return datetime.datetime.fromisoformat(dt_value)
            except ValueError:
                # Try a different format
                try:
                    return datetime.datetime.strptime(dt_value, "%Y-%m-%d %H:%M:%S.%f")
                except ValueError:
                    logger.error(f"Could not parse datetime string: {dt_value}")
                    # Return current time as fallback
                    return datetime.datetime.now()
        else:
            logger.error(f"Unknown datetime format: {type(dt_value)}")
            return datetime.datetime.now()
    
    @app_commands.command(name="pay_installment", description="Make an installment payment for a loan")
    @app_commands.describe(
        loan_id="The ID of the loan to pay an installment for (4-digit number)",
        amount="Amount to pay (must be at least the minimum installment amount)"
    )
    async def pay_installment(self, interaction: discord.Interaction, loan_id: str, amount: int):
        """Command to make an installment payment toward a loan"""
        try:
            # Defer the reply first to prevent interaction timeout
            await interaction.response.defer()
            
            if not loan_id:
                return await interaction.followup.send(
                    "Please provide a valid loan ID."
                )
            
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id)
            
            # Log the installment payment attempt
            logger.info(f"Installment payment attempt by {interaction.user} (ID: {user_id}) for loan ID: {loan_id} in guild {guild_id}")
            
            # Get loan database from bot
            loan_database = self.bot.loan_database
            
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
                        logger.warning(f"User {user_id} attempted to pay installment for loan {loan_id} belonging to user {loan.get('user_id')}")
            
            if loan_index == -1:
                logger.warning(f"Loan not found. ID: {loan_id}, User ID: {user_id}")
                return await interaction.followup.send(
                    f"Loan #{loan_id} not found or you are not the borrower of this loan. Please check the loan ID and try again."
                )
            
            loan = loan_database["loans"][loan_index]
            
            # Check if loan is already repaid
            if loan.get("status") not in ["active", "active_partial"]:
                logger.warning(f"Attempted to pay installment for loan #{loan_id} with status: {loan.get('status')}")
                return await interaction.followup.send(
                    f"Loan #{loan_id} cannot receive installment payments because it is marked as {loan.get('status', 'unknown')}."
                )
            
            # Check if installments are enabled for this loan
            if not loan.get("installment_enabled", False):
                logger.warning(f"Attempted to pay installment for non-installment loan #{loan_id}")
                return await interaction.followup.send(
                    f"Loan #{loan_id} does not support installment payments. Please use `/repay {loan_id}` to repay the full amount."
                )
            
            logger.info(f"Processing installment payment for loan: {loan}")
            
            # Check if repayment is late and calculate late fee if applicable
            current_date = datetime.datetime.now()
            due_date = self._parse_datetime(loan["due_date"])
            on_time = current_date <= due_date
            late_fee = 0
            
            if not on_time and not loan.get("late_fee_applied", False):
                # Apply 5% late fee
                late_fee = round(loan["amount"] * 0.05)
                loan["late_fee"] = late_fee
                loan["total_repayment"] += late_fee
                loan["late_fee_applied"] = True
                logger.info(f"Late fee applied: {late_fee}, new total: {loan['total_repayment']}")
            
            # Initialize amount_repaid if not present
            if "amount_repaid" not in loan:
                loan["amount_repaid"] = 0
            
            # Calculate remaining balance
            remaining_balance = loan["total_repayment"] - loan["amount_repaid"]
            
            # Check if amount is too small (minimum installment)
            min_installment = loan.get("min_installment_amount", 1000)
            if amount < min_installment and amount < remaining_balance:
                logger.warning(f"Installment amount too small. Provided: {amount}, Minimum: {min_installment}")
                return await interaction.followup.send(
                    f"Installment amount is too small. The minimum installment for this loan is "
                    f"{min_installment} {config.UNBELIEVABOAT['CURRENCY_NAME']} or the remaining balance."
                )
            
            # Cap amount at the remaining balance
            if amount > remaining_balance:
                amount = remaining_balance
                logger.info(f"Capped installment amount to remaining balance: {remaining_balance}")
            
            # Set to full repayment if this will pay off the loan
            full_repayment = (amount >= remaining_balance)
            
            # For partial payments, set the amount to process
            payment_amount = amount
            
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
                    
                    logger.info(f"User balance: {user_balance.get('cash', 0)}, Required: {payment_amount}")
                    
                    # Check if user has enough currency
                    if user_balance.get("cash", 0) < payment_amount:
                        return await interaction.followup.send(
                            f"You don't have enough {config.UNBELIEVABOAT['CURRENCY_NAME']} to make this payment. "
                            f"You need {payment_amount} {config.UNBELIEVABOAT['CURRENCY_NAME']} but only have {user_balance.get('cash', 0)}."
                        )
                    
                    # Generate payment description
                    if not full_repayment:
                        payment_description = f"Loan #{loan_id} installment payment - {amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}"
                    else:
                        payment_description = (f"Loan #{loan_id} final installment - {amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}")
                    
                    logger.info(f"Removing {payment_amount} from user {user_id} in guild {guild_id}")
                    
                    # Remove the payment amount from user's balance
                    result = await unbelievaboat.remove_currency(
                        guild_id,
                        user_id,
                        payment_amount,
                        payment_description
                    )
                    
                    if not result:
                        logger.error(f"Failed to remove currency from user {user_id} in guild {guild_id}")
                        return await interaction.followup.send(
                            "There was an error processing your payment with UnbelievaBoat. Please try again or contact an admin."
                        )
                    
                    # Add UnbelievaBoat transaction info to the loan
                    loan["unbelievaboat"] = loan.get("unbelievaboat", {})
                    
                    if "transactions" not in loan["unbelievaboat"]:
                        loan["unbelievaboat"]["transactions"] = []
                        
                    # Record this transaction
                    transaction = {
                        "type": "installment" if not full_repayment else "final_installment",
                        "amount": payment_amount,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "remaining_balance": user_balance.get("cash", 0)
                    }
                    
                    loan["unbelievaboat"]["transactions"].append(transaction)
                    
                    # Track repayment in the loan
                    loan["amount_repaid"] = loan.get("amount_repaid", 0) + payment_amount
                    
                    # Check if the loan is now fully repaid
                    if full_repayment:
                        loan["status"] = "repaid"
                        loan["repayment_date"] = datetime.datetime.now().isoformat()
                        
                        # Move to history if fully repaid
                        if "history" not in loan_database:
                            loan_database["history"] = []
                        
                        # Add to history but keep it in loans array for now
                        # The repay.py command will clean it up if needed
                        loan_database["history"].append(loan.copy())
                    else:
                        # Update status to show partial payment
                        loan["status"] = "active_partial"
                        loan["last_payment_date"] = datetime.datetime.now().isoformat()
                        
                    # Update credit score
                    credit_change = 10 if on_time else -5
                    
                    if "credit_scores" not in loan_database:
                        loan_database["credit_scores"] = {}
                    
                    if user_id not in loan_database["credit_scores"]:
                        loan_database["credit_scores"][user_id] = 100  # Default score
                    
                    loan_database["credit_scores"][user_id] += credit_change
                    logger.info(f"Updated credit score for user {user_id}: {loan_database['credit_scores'][user_id]} (change: {credit_change})")
                    
                    # Create embed for payment details
                    embed = discord.Embed(
                        title="💰 Installment Payment Processed" if not full_repayment else "💰 Final Payment Processed",
                        description="Thank you for your payment!",
                        color=0x00FF00
                    )
                    
                    embed.add_field(name="Loan ID", value=f"{loan_id}", inline=True)
                    embed.add_field(name="Amount Paid", value=f"{payment_amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
                    
                    if not full_repayment:
                        # For partial payments, show remaining balance
                        remaining = loan["total_repayment"] - loan["amount_repaid"]
                        embed.add_field(name="Remaining Balance", value=f"{remaining} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
                        embed.add_field(name="Total Repaid", value=f"{loan['amount_repaid']} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
                        
                        # Progress bar for visualization
                        progress = int((loan["amount_repaid"] / loan["total_repayment"]) * 10)
                        progress_bar = "▰" * progress + "▱" * (10 - progress)
                        percent = int((loan["amount_repaid"] / loan["total_repayment"]) * 100)
                        
                        embed.add_field(
                            name="Repayment Progress", 
                            value=f"{progress_bar} {percent}%", 
                            inline=False
                        )
                        
                        # Include note about future payments
                        embed.set_footer(text=f"Use /pay_installment {loan_id} [amount] to make another payment.")
                    else:
                        embed.add_field(name="Status", value="Fully Repaid", inline=True)
                        embed.add_field(name="Credit Score Change", value=f"+{credit_change}" if credit_change > 0 else f"{credit_change}", inline=True)
                        embed.set_footer(text="Your loan has been fully repaid. Thank you!")
                    
                    # Send response
                    await interaction.followup.send(embed=embed)
                    
                    logger.info(f"Installment payment for Loan #{loan_id} successfully processed")
                    
                except Exception as error:
                    logger.error(f"Error in installment payment: {str(error)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    
                    try:
                        await interaction.followup.send(
                            f"An error occurred while processing your payment: {str(error)}"
                        )
                    except:
                        logger.error("Failed to send error message")
            else:
                # Manual mode without UnbelievaBoat API
                # Just update the loan status
                # Track repayment in the loan
                loan["amount_repaid"] = loan.get("amount_repaid", 0) + payment_amount
                
                # Check if the loan is now fully repaid
                if full_repayment:
                    loan["status"] = "repaid"
                    loan["repayment_date"] = datetime.datetime.now().isoformat()
                    
                    # Move to history if fully repaid
                    if "history" not in loan_database:
                        loan_database["history"] = []
                    
                    # Add to history but keep it in loans array for now
                    loan_database["history"].append(loan.copy())
                else:
                    # Update status to show partial payment
                    loan["status"] = "active_partial"
                    loan["last_payment_date"] = datetime.datetime.now().isoformat()
                
                # Update credit score
                credit_change = 10 if on_time else -5
                
                if "credit_scores" not in loan_database:
                    loan_database["credit_scores"] = {}
                
                if user_id not in loan_database["credit_scores"]:
                    loan_database["credit_scores"][user_id] = 100  # Default score
                
                loan_database["credit_scores"][user_id] += credit_change
                
                # Create embed for manual payment details
                embed = discord.Embed(
                    title="💰 Installment Payment Recorded" if not full_repayment else "💰 Final Payment Recorded",
                    description="Thank you for your payment!",
                    color=0x00FF00
                )
                
                embed.add_field(name="Loan ID", value=f"{loan_id}", inline=True)
                embed.add_field(name="Amount Paid", value=f"{payment_amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
                
                if not full_repayment:
                    # For partial payments, show remaining balance
                    remaining = loan["total_repayment"] - loan["amount_repaid"]
                    embed.add_field(name="Remaining Balance", value=f"{remaining} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
                    embed.add_field(name="Total Repaid", value=f"{loan['amount_repaid']} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
                    
                    # Progress bar for visualization
                    progress = int((loan["amount_repaid"] / loan["total_repayment"]) * 10)
                    progress_bar = "▰" * progress + "▱" * (10 - progress)
                    percent = int((loan["amount_repaid"] / loan["total_repayment"]) * 100)
                    
                    embed.add_field(
                        name="Repayment Progress", 
                        value=f"{progress_bar} {percent}%", 
                        inline=False
                    )
                    
                    # Include note about future payments
                    embed.set_footer(text=f"Use /pay_installment {loan_id} [amount] to make another payment.")
                else:
                    embed.add_field(name="Status", value="Fully Repaid", inline=True)
                    embed.add_field(name="Credit Score Change", value=f"+{credit_change}" if credit_change > 0 else f"{credit_change}", inline=True)
                    embed.set_footer(text="Your loan has been fully repaid. Thank you!")
                
                # Send response
                await interaction.followup.send(embed=embed)
                
                # If manual mode and API is not enabled, give instructions
                if manual_integration:
                    instructions_embed = manual_integration.format_payment_instructions(
                        loan_id,
                        payment_amount
                    )
                    
                    await interaction.followup.send(
                        content="Please follow these steps to complete your payment:",
                        embed=instructions_embed
                    )
        
        except Exception as e:
            logger.error(f"Error in pay_installment command: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await interaction.followup.send(
                "There was an error processing your installment payment. Please try again or contact an admin."
            )
            
    @app_commands.command(name="pending_payments", description="View all your pending loan installments")
    async def pending_payments(self, interaction: discord.Interaction):
        """Command to view all loans with pending installment payments"""
        # Defer the reply first to prevent interaction timeout
        await interaction.response.defer()
        
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        # Get loan database from bot
        loan_database = self.bot.loan_database
        
        # Find the user's active loans with installment payments
        installment_loans = []
        
        if "loans" in loan_database and loan_database["loans"]:
            for loan in loan_database["loans"]:
                if (loan and loan.get("user_id") == user_id and 
                    loan.get("guild_id") == guild_id and 
                    (loan.get("status") == "active" or loan.get("status") == "active_partial") and
                    loan.get("installment_enabled", False)):
                    installment_loans.append(loan)
        
        if not installment_loans:
            return await interaction.followup.send(
                "You don't have any active loans with pending installment payments.",
                ephemeral=True
            )
        
        # Create embed for installment loan details
        embed = discord.Embed(
            title="💳 Your Installment Loans",
            description=f"You have {len(installment_loans)} active installment loans with pending payments.",
            color=0x0099FF
        )
        
        for loan in installment_loans:
            loan_id = loan.get("id", "Unknown")
            amount = loan.get("amount", 0)
            total_repayment = loan.get("total_repayment", 0)
            due_date = self._parse_datetime(loan.get("due_date", datetime.datetime.now()))
            
            # Get installment details
            amount_repaid = loan.get("amount_repaid", 0)
            remaining_balance = total_repayment - amount_repaid
            min_payment = loan.get("min_installment_amount", 1000)
            
            # Format the due date as a Discord timestamp
            timestamp = int(due_date.timestamp())
            
            # Determine if loan is late
            is_late = datetime.datetime.now() > due_date
            status = "**OVERDUE - PAYMENT REQUIRED**" if is_late else ("Partially Repaid" if loan.get("status") == "active_partial" else "Awaiting First Payment")
            
            # Get payment progress
            if amount_repaid > 0:
                progress = int((amount_repaid / total_repayment) * 10)
                progress_bar = "▰" * progress + "▱" * (10 - progress)
                percent = int((amount_repaid / total_repayment) * 100)
                progress_text = f"{progress_bar} {percent}%"
            else:
                progress_text = "No payments made yet"
            
            # Create field value with detailed loan info
            field_value = (
                f"**Original Amount:** {amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                f"**Total Repayment:** {total_repayment} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                f"**Amount Repaid:** {amount_repaid} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                f"**Remaining Balance:** {remaining_balance} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                f"**Minimum Payment:** {min_payment} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                f"**Due Date:** <t:{timestamp}:F>\n"
                f"**Status:** {status}\n"
                f"**Progress:** {progress_text}\n\n"
                f"Use `/pay_installment {loan_id} [amount]` to make a payment."
            )
            
            embed.add_field(
                name=f"Loan #{loan_id}",
                value=field_value,
                inline=False
            )
        
        # Create a view with payment buttons
        view = discord.ui.View()
        
        # Add buttons for each loan (limit to 5 to avoid hitting the button limit)
        for loan in installment_loans[:5]:
            loan_id = loan.get("id", "Unknown")
            
            # Add installment payment button
            pay_button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=f"Pay Loan #{loan_id} Installment",
                custom_id=f"installment_{user_id}_{loan_id}"
            )
            
            view.add_item(pay_button)
        
        # Send the response
        await interaction.followup.send(embed=embed, view=view)
    
    # Button handler for installment payments
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle button interactions for installment payments"""
        if not interaction.data or not interaction.data.get("custom_id"):
            return
        
        custom_id = interaction.data.get("custom_id", "")
        
        # Check if this is an installment payment button
        if custom_id.startswith("installment_"):
            parts = custom_id.split("_")
            if len(parts) < 3:
                return
            
            intended_user_id = parts[1]
            loan_id = parts[2]
            
            # Verify this is the correct user
            if str(interaction.user.id) != intended_user_id:
                return await interaction.response.send_message(
                    "This button is not for you. Only the loan holder can make installment payments.",
                    ephemeral=True
                )
            
            # Get the loan details
            loan_database = self.bot.loan_database
            
            # Find the loan
            loan = None
            for l in loan_database.get("loans", []):
                if l and l.get("id") == loan_id and l.get("user_id") == intended_user_id:
                    loan = l
                    break
            
            if not loan:
                return await interaction.response.send_message(
                    f"Loan #{loan_id} not found or has already been repaid.",
                    ephemeral=True
                )
            
            # Open a modal to ask for payment amount
            modal = discord.ui.Modal(title="Installment Payment")
            
            # Calculate remaining balance
            amount_repaid = loan.get("amount_repaid", 0)
            remaining_balance = loan.get("total_repayment", 0) - amount_repaid
            min_payment = loan.get("min_installment_amount", 1000)
            
            # Add payment amount input field
            amount_input = discord.ui.TextInput(
                label=f"Payment amount (min: {min_payment})",
                placeholder=f"Enter amount between {min_payment} and {remaining_balance}",
                required=True,
                style=discord.TextStyle.short
            )
            modal.add_item(amount_input)
            
            async def modal_callback(modal_interaction):
                try:
                    amount_value = amount_input.value.strip()
                    amount = int(amount_value)
                    
                    # Execute the pay_installment command
                    await self.pay_installment(modal_interaction, loan_id, amount)
                except ValueError:
                    await modal_interaction.response.send_message(
                        "Please enter a valid number for the payment amount.",
                        ephemeral=True
                    )
                except Exception as e:
                    logger.error(f"Error in installment modal: {e}")
                    await modal_interaction.response.send_message(
                        "There was an error processing your payment. Please try again.",
                        ephemeral=True
                    )
            
            modal.on_submit = modal_callback
            await interaction.response.send_modal(modal)


async def setup(bot):
    await bot.add_cog(InstallmentCommand(bot)) 