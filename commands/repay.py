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
        loan_id="The ID of the loan to repay (4-digit number)"
    )
    async def repay(self, interaction: discord.Interaction, loan_id: str):
        """Command to repay a loan"""
        try:
            # Check if interaction is already responded to
            if interaction.response.is_done():
                logger.warning("Interaction already acknowledged in repay command, using followup instead")
                send_message = interaction.followup.send
            else:
                # Defer the reply first to prevent interaction timeout
                await interaction.response.defer()
                send_message = interaction.followup.send
            
            if not loan_id:
                return await send_message(
                    "Please provide a valid loan ID.",
                    ephemeral=True
                )
            
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id)
            
            # Get loan database from bot
            loan_database = self.bot.loan_database
            
            # Find the loan
            if "loans" not in loan_database or not isinstance(loan_database["loans"], list):
                loan_database["loans"] = []
                print(f"Loans array did not exist in database, initialized empty array")
            
            # Find loan index
            loan_index = -1
            for i, loan in enumerate(loan_database["loans"]):
                if loan and loan.get("id") == loan_id:
                    # First check if this user is the borrower
                    if loan.get("user_id") == user_id:
                        loan_index = i
                        break
                    else:
                        return await send_message(
                            f"You cannot repay a loan that belongs to someone else.",
                            ephemeral=True
                        )
            
            if loan_index == -1:
                return await send_message(
                    f"Loan #{loan_id} not found or already repaid. Please check the loan ID and try again.",
                    ephemeral=True
                )
            
            loan = loan_database["loans"][loan_index]
            
            if loan.get("status") != "active" and loan.get("status") != "active_partial":
                return await send_message(
                    f"Loan #{loan_id} is marked as {loan.get('status', 'unknown')} and cannot be repaid.",
                    ephemeral=True
                )
            
            # Calculate the repayment amount
            repayment_amount = loan.get("total_repayment", 0)
            if "amount_repaid" in loan:
                repayment_amount -= loan.get("amount_repaid", 0)
            
            # Check if repayment is late and calculate late fee if applicable
            current_date = datetime.datetime.now()
            due_date = self._parse_datetime(loan["due_date"])
            on_time = current_date <= due_date
            late_fee = 0
            
            if not on_time and not loan.get("late_fee_applied", False):
                # Apply 5% late fee if not already applied
                late_fee = round(loan["amount"] * 0.05)
                loan["late_fee"] = late_fee
                loan["total_repayment"] = loan.get("total_repayment", 0) + late_fee
                loan["late_fee_applied"] = True
                
                # Recalculate repayment amount with late fee
                repayment_amount = loan.get("total_repayment", 0)
                if "amount_repaid" in loan:
                    repayment_amount -= loan.get("amount_repaid", 0)
            
            # Check if this loan allows installments and inform the user
            if loan.get("installment_enabled", False):
                return await send_message(
                    f"Loan #{loan_id} is set up for installment payments. "
                    f"Please use `/pay_installment {loan_id} [amount]` to make a payment.",
                    ephemeral=True
                )
            
            # If the API is enabled and not in manual mode, process the payment through the API
            if config.UNBELIEVABOAT["ENABLED"] and unbelievaboat:
                try:
                    # First check if the user has enough money
                    user_balance = await unbelievaboat.get_user_balance(guild_id, user_id)
                    
                    if not user_balance:
                        return await send_message(
                            "Unable to check your balance with UnbelievaBoat. Please try again or contact an admin.",
                            ephemeral=True
                        )
                    
                    if user_balance.get("cash", 0) < repayment_amount:
                        return await send_message(
                            f"You don't have enough {config.UNBELIEVABOAT['CURRENCY_NAME']} to repay this loan. "
                            f"You need {repayment_amount:,} {config.UNBELIEVABOAT['CURRENCY_NAME']} but only have {user_balance.get('cash', 0):,}.",
                            ephemeral=True
                        )
                    
                    # Generate a payment description for the API
                    payment_description = f"Loan #{loan_id} repayment"
                    
                    # Add the total amount with any late fees
                    if late_fee > 0:
                        payment_description += f" (includes {late_fee} late fee)"
                    
                    # Remove the money from the user
                    result = await unbelievaboat.remove_currency(
                        guild_id,
                        user_id,
                        repayment_amount,
                        payment_description
                    )
                    
                    if not result:
                        return await send_message(
                            "There was an error processing your payment with UnbelievaBoat. Please try again or contact an admin.",
                            ephemeral=True
                        )
                    
                    # Mark the loan as repaid
                    loan["status"] = "repaid"
                    loan["repayment_date"] = current_date.isoformat()
                    
                    # Add information about the repayment
                    loan["repaid"] = True
                    loan["repayment_on_time"] = on_time
                    loan["repayment_late_fee"] = late_fee
                    
                    # Add UnbelievaBoat transaction info to the loan
                    loan["unbelievaboat"] = loan.get("unbelievaboat", {})
                    loan["unbelievaboat"]["repayment_transaction"] = result
                    
                    # Move the loan to history
                    if "history" not in loan_database:
                        loan_database["history"] = []
                    
                    loan_database["history"].append(loan)
                    
                    # Update the user's credit score
                    credit_change = 10 if on_time else -5  # +10 for on-time, -5 for late
                    
                    if "credit_scores" not in loan_database:
                        loan_database["credit_scores"] = {}
                    
                    if user_id not in loan_database["credit_scores"]:
                        loan_database["credit_scores"][user_id] = 100  # Default score
                        
                    loan_database["credit_scores"][user_id] += credit_change
                    
                    # Create a nice embed for the repayment confirmation
                    embed = discord.Embed(
                        title="💰 Loan Repaid Successfully",
                        description=f"You have successfully repaid your loan of {loan['amount']:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}.",
                        color=0x00FF00  # Green
                    )
                    
                    embed.add_field(
                        name="Loan ID",
                        value=loan_id,
                        inline=True
                    )
                    
                    embed.add_field(
                        name="Amount Repaid",
                        value=f"{repayment_amount:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
                        inline=True
                    )
                    
                    if late_fee > 0:
                        embed.add_field(
                            name="Late Fee",
                            value=f"{late_fee:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
                            inline=True
                        )
                    
                    embed.add_field(
                        name="Repayment Status",
                        value=f"{'✅ On Time' if on_time else '❌ Late'}",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="Credit Score Change",
                        value=f"{'+' if credit_change > 0 else ''}{credit_change}",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="New Credit Score",
                        value=f"{loan_database['credit_scores'][user_id]}",
                        inline=True
                    )
                    
                    # Remove the loan from the active loans array
                    loan_database["loans"].pop(loan_index)
                    
                    # Send the confirmation
                    await send_message(embed=embed)
                    
                    # Log the repayment
                    print(f"Loan #{loan_id} for {loan['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']} repaid by user {user_id}")
                    
                except Exception as e:
                    import traceback
                    print(f"Error in loan repayment: {str(e)}")
                    print(traceback.format_exc())
                    return await send_message(
                        f"An error occurred while processing your repayment: {str(e)}",
                        ephemeral=True
                    )
            else:
                # Manual mode - Provide instructions for repayment
                # Send a confirmation first that we'll process the repayment
                embed = discord.Embed(
                    title="💰 Manual Loan Repayment",
                    description=f"Please follow these steps to repay your loan of {loan['amount']:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}.",
                    color=0x0099FF  # Blue
                )
                
                embed.add_field(
                    name="Loan ID",
                    value=loan_id,
                    inline=True
                )
                
                embed.add_field(
                    name="Amount Due",
                    value=f"{repayment_amount:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
                    inline=True
                )
                
                if late_fee > 0:
                    embed.add_field(
                        name="Late Fee",
                        value=f"{late_fee:,} {config.UNBELIEVABOAT['CURRENCY_NAME']} (included in amount due)",
                        inline=True
                    )
                
                # Get the manual repayment instructions
                if manual_integration:
                    instruction_embed = manual_integration.format_payment_instructions(
                        loan_id,
                        repayment_amount
                    )
                    
                    # Send the instructions
                    await send_message(
                        content="Please complete the steps below to repay your loan:",
                        embed=instruction_embed
                    )
                else:
                    embed.add_field(
                        name="Next Steps",
                        value=(
                            f"Since UnbelievaBoat integration is not enabled, please contact a server administrator "
                            f"to complete your repayment manually."
                        ),
                        inline=False
                    )
                    
                    await send_message(embed=embed)
                
                # Mark loan as manual repayment in progress
                loan["status"] = "manual_repayment"
                loan["manual_repayment_started"] = current_date.isoformat()
        except Exception as e:
            logger.error(f"Error in repay command: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Check if we can still respond
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "There was an error processing your repayment. Please try again or contact an admin.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "There was an error processing your repayment. Please try again or contact an admin.",
                        ephemeral=True
                    )
            except Exception as e2:
                logger.error(f"Error sending error message: {e2}")
                pass

    # Button handler for repayment
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        try:
            if not interaction.data or not interaction.data.get("custom_id"):
                return
            
            custom_id = interaction.data.get("custom_id", "")
            
            # Check if this is a repay button
            if custom_id.startswith("repay_"):
                parts = custom_id.split("_")
                if len(parts) < 3:
                    return
                
                loan_id = parts[2]
                user_id = parts[1]
                
                # Verify this is the correct user
                if str(interaction.user.id) != user_id:
                    try:
                        await interaction.response.send_message(
                            "This button is not for you. Only the loan holder can repay.",
                            ephemeral=True
                        )
                    except discord.errors.HTTPException as e:
                        if e.code == 40060:  # Interaction already acknowledged
                            await interaction.followup.send(
                                "This button is not for you. Only the loan holder can repay.",
                                ephemeral=True
                            )
                    return
                
                # Call the repay command
                await self.repay(interaction, loan_id)
        except Exception as e:
            logger.error(f"Error in repay button handler: {e}")
            import traceback
            logger.error(traceback.format_exc())


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