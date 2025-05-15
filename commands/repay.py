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
        
    @app_commands.command(name="repay", description="Repay a loan")
    @app_commands.describe(
        loan_id="The ID of the loan to repay (4-digit number)",
        amount="Amount to repay (optional for installment payments)"
    )
    async def repay(self, interaction: discord.Interaction, loan_id: str, amount: int = None):
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
            due_date = self._parse_datetime(loan["due_date"])
            on_time = current_date <= due_date
            late_fee = 0
            
            if not on_time:
                # Apply 5% late fee
                late_fee = round(loan["amount"] * 0.05)
                loan["late_fee"] = late_fee
                loan["total_repayment"] += late_fee
                logger.info(f"Late fee applied: {late_fee}, new total: {loan['total_repayment']}")
            
            # Check if this is an installment payment
            is_installment = loan.get("installment_enabled", False) and amount is not None
            
            # If installment payment, validate amount
            if is_installment:
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
                    logger.info(f"Capped repayment amount to remaining balance: {remaining_balance}")
                
                # Set to full repayment if this will pay off the loan
                full_repayment = (amount >= remaining_balance)
                
                # For partial payments, set the amount to process
                payment_amount = amount
            else:
                # Full repayment
                full_repayment = True
                payment_amount = loan["total_repayment"]
                amount = payment_amount  # Set amount for later reference
            
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
                    
                    # Generate appropriate payment description based on payment type
                    if is_installment and not full_repayment:
                        payment_description = f"Loan #{loan_id} installment payment - {amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}"
                    else:
                        payment_description = (f"Loan #{loan_id} repayment - {loan['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']} + "
                                              f"{loan['interest']} interest{' + ' + str(late_fee) + ' late fee' if late_fee > 0 else ''}")
                    
                    logger.info(f"Removing {payment_amount} from user {user_id} in guild {guild_id}")
                    
                    # Remove the repayment amount from user's balance
                    result = await unbelievaboat.remove_currency(
                        guild_id,
                        user_id,
                        payment_amount,
                        payment_description
                    )
                    
                    if not result:
                        logger.error(f"Failed to remove currency from user {user_id} in guild {guild_id}")
                        return await interaction.followup.send(
                            "There was an error processing your repayment with UnbelievaBoat. Please try again or contact an admin."
                        )
                    
                    # Add UnbelievaBoat transaction info to the loan
                    loan["unbelievaboat"] = loan.get("unbelievaboat", {})
                    
                    if "transactions" not in loan["unbelievaboat"]:
                        loan["unbelievaboat"]["transactions"] = []
                        
                    # Record this transaction
                    transaction = {
                        "type": "installment" if is_installment and not full_repayment else "repayment",
                        "amount": payment_amount,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "remaining_balance": user_balance.get("cash", 0)
                    }
                    
                    loan["unbelievaboat"]["transactions"].append(transaction)
                    
                    # Track repayment in the loan
                    if is_installment:
                        # Add to the amount repaid
                        loan["amount_repaid"] = loan.get("amount_repaid", 0) + payment_amount
                        
                        # Check if the loan is now fully repaid
                        if full_repayment:
                            loan["status"] = "repaid"
                            loan["repayment_date"] = datetime.datetime.now().isoformat()
                        else:
                            # Update status to show partial payment
                            loan["status"] = "active_partial"
                            loan["last_payment_date"] = datetime.datetime.now().isoformat()
                            
                            # Calculate remaining amount
                            remaining = loan["total_repayment"] - loan["amount_repaid"]
                    else:
                        # For full immediate repayment
                        loan["status"] = "repaid"
                        loan["repayment_date"] = datetime.datetime.now().isoformat()
                        loan["amount_repaid"] = loan["total_repayment"]
                    
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
                        title="💰 Payment Processed" if is_installment and not full_repayment else "💰 Loan Repaid",
                        description="Thank you for your payment!" if is_installment and not full_repayment else "Thank you for repaying your loan!",
                        color=0x00FF00
                    )
                    
                    embed.add_field(name="Loan ID", value=f"{loan_id}", inline=True)
                    embed.add_field(name="Amount Paid", value=f"{payment_amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
                    
                    if is_installment and not full_repayment:
                        # For partial payments, show remaining balance
                        remaining = loan["total_repayment"] - loan["amount_repaid"]
                        embed.add_field(name="Remaining Balance", value=f"{remaining} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
                        embed.add_field(name="Total Repaid", value=f"{loan['amount_repaid']} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
                        
                        # Include note about future payments
                        embed.set_footer(text=f"Use /repay {loan_id} [amount] to make another payment.")
                    else:
                        embed.add_field(name="Status", value="Fully Repaid", inline=True)
                        embed.set_footer(text="Your loan has been fully repaid.")
                    
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
        """Handle button interactions for loan repayment"""
        if not interaction.data or not interaction.data.get("custom_id"):
            return
            
            custom_id = interaction.data.get("custom_id", "")
            
        # Check if this is a repay button
        if custom_id.startswith("repay_"):
            parts = custom_id.split("_")
            if len(parts) < 3:
                return
            
            intended_user_id = parts[1]
            loan_id = parts[2]
            
            # Verify this is the correct user
            if str(interaction.user.id) != intended_user_id:
                return await interaction.response.send_message(
                    "This button is not for you. Only the loan holder can repay this loan.",
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
            
            # Check if installment payments are enabled for this loan
            is_installment = loan.get("installment_enabled", False)
            
            if is_installment:
                # For installment loans, open a modal to ask for payment amount
                modal = discord.ui.Modal(title="Loan Repayment")
                
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
                        
                        # Execute the repay command
                        await self.repay(modal_interaction, loan_id, amount)
                    except ValueError:
                        await modal_interaction.response.send_message(
                            "Please enter a valid number for the payment amount.",
                            ephemeral=True
                        )
                    except Exception as e:
                        logger.error(f"Error in repay modal: {e}")
                        await modal_interaction.response.send_message(
                            "There was an error processing your payment. Please try again.",
                            ephemeral=True
                        )
                
                modal.on_submit = modal_callback
                await interaction.response.send_modal(modal)
            else:
                # For standard loans, just execute the repay command directly
                await interaction.response.defer()
                await self.repay(interaction, loan_id)


class LoanViewCommand(commands.Cog):
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
        
    @app_commands.command(name="viewloans", description="View all your active loans")
    async def viewloans(self, interaction: discord.Interaction):
        # Defer the reply first to prevent interaction timeout
        await interaction.response.defer()
        
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        # Get loan database from bot
        loan_database = self.bot.loan_database
        
        # Find the user's active loans
        active_loans = []
        
        if "loans" in loan_database and loan_database["loans"]:
            for loan in loan_database["loans"]:
                if (loan and loan.get("user_id") == user_id and 
                    loan.get("guild_id") == guild_id and 
                    (loan.get("status") == "active" or loan.get("status") == "active_partial")):
                    active_loans.append(loan)
        
        if not active_loans:
            return await interaction.followup.send(
                "You don't have any active loans at the moment.",
                ephemeral=True
            )
        
        # Create embed for loan details
        embed = discord.Embed(
            title="🏦 Your Active Loans",
            description=f"You have {len(active_loans)} active loans.",
            color=0x0099FF
        )
        
        for loan in active_loans:
            loan_id = loan.get("id", "Unknown")
            amount = loan.get("amount", 0)
            interest = loan.get("interest", 0)
            total_repayment = loan.get("total_repayment", 0)
            due_date = self._parse_datetime(loan.get("due_date", datetime.datetime.now()))
            
            # Check if this is an installment loan
            is_installment = loan.get("installment_enabled", False)
            amount_repaid = loan.get("amount_repaid", 0)
            remaining_balance = total_repayment - amount_repaid
            
            # Format the due date as a Discord timestamp
            timestamp = int(due_date.timestamp())
            
            # Determine if loan is late
            is_late = datetime.datetime.now() > due_date
            status = "**OVERDUE**" if is_late else ("Partially Repaid" if loan.get("status") == "active_partial" else "Active")
            
            # Create field value with loan details
            field_value = (
                f"**Amount:** {amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                f"**Interest:** {interest} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                f"**Total Repayment:** {total_repayment} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
            )
            
            # Add installment information if enabled
            if is_installment:
                field_value += (
                    f"**Amount Repaid:** {amount_repaid} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                    f"**Remaining Balance:** {remaining_balance} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                    f"**Minimum Payment:** {loan.get('min_installment_amount', 0)} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                )
            
            field_value += (
                f"**Due Date:** <t:{timestamp}:F>\n"
                f"**Status:** {status}\n\n"
                f"Use `/repay {loan_id}" + (f" [amount]" if is_installment else "") + "` to repay this loan."
            )
            
            embed.add_field(
                name=f"Loan #{loan_id}",
                value=field_value,
                inline=False
            )
        
        # Create a view with buttons
        view = discord.ui.View()
        
        # Add buttons for each loan (limit to 5 to avoid hitting the button limit)
        for loan in active_loans[:5]:
            loan_id = loan.get("id", "Unknown")
            
            # Add repay button
            repay_button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=f"Repay Loan #{loan_id}",
                custom_id=f"repay_{user_id}_{loan_id}"
            )
            
            view.add_item(repay_button)
        
        # Send the response
        await interaction.followup.send(embed=embed, view=view)
        

async def setup(bot):
    await bot.add_cog(RepayCommand(bot))
    await bot.add_cog(LoanViewCommand(bot)) 