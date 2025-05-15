import discord
from discord import app_commands
from discord.ext import commands
import datetime
import random
import config
import sys
import os
import logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import server settings for captain role check
import server_settings

# Initialize UnbelievaBoat integration
unbelievaboat = None

# Logger for this module
logger = logging.getLogger("loan")

# Try to get port configuration from environment
unbelievaboat_port = None
try:
    port_env = os.environ.get('UNBELIEVABOAT_PORT')
    if port_env:
        unbelievaboat_port = int(port_env)
        logger.info(f"Using UnbelievaBoat port from environment: {unbelievaboat_port}")
except (ValueError, TypeError) as e:
    logger.warning(f"Invalid UNBELIEVABOAT_PORT environment variable: {e}")

if config.UNBELIEVABOAT["ENABLED"]:
    try:
        from unbelievaboat_integration import UnbelievaBoatAPI
        api_key = config.UNBELIEVABOAT["API_KEY"]
        
        # Check if API key is valid format
        if not api_key or len(api_key.strip()) < 10:
            logger.error(f"UnbelievaBoat API key is invalid or too short: {api_key[:5]}... Length: {len(api_key) if api_key else 0}")
            logger.error("Please set a valid API key in the config or environment variables.")
        else:
            logger.info(f"Initializing UnbelievaBoat API with token starting with: {api_key[:10]}...")
            
            unbelievaboat = UnbelievaBoatAPI(
                api_key=api_key,
                port=unbelievaboat_port,
                timeout=45  # Increased timeout for Render
            )
            logger.info(f"UnbelievaBoat API integration enabled with base URL: {unbelievaboat.base_url}")
            
            # Add diagnostic info
            if unbelievaboat_port:
                logger.info(f"Using custom port: {unbelievaboat_port}")
    except ImportError as e:
        logger.error(f"Failed to import UnbelievaBoat API integration: {e}")
    except Exception as e:
        logger.error(f"Error initializing UnbelievaBoat API: {e}")
        import traceback
        logger.error(traceback.format_exc())
else:
    logger.info("UnbelievaBoat API integration disabled in config")

# Always import manual integration as fallback
try:
    import manual_unbelievaboat as manual_integration
    logger.info("Manual integration module loaded as fallback")
except ImportError as e:
    logger.error(f"Failed to import manual integration module: {e}")
    manual_integration = None


def generate_loan_id(existing_loans):
    """
    Generate a unique 4-digit loan ID
    :param existing_loans: List of existing loans
    :return: Unique loan ID as string
    """
    min_id = 1000
    max_id = 9999
    
    # Ensure existing_loans is a list
    if not existing_loans or not isinstance(existing_loans, list):
        existing_loans = []
    
    # Keep generating until we find a unique ID
    while True:
        loan_id = str(random.randint(min_id, max_id))
        
        # Check if this ID already exists in loans
        exists = any(loan and loan.get('id') == loan_id for loan in existing_loans)
        
        if not exists:
            return loan_id


class LoanCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    async def _check_can_request_loan(self, interaction):
        """Check if a user can request a loan"""
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        # Get captain role ID
        captain_role_id = server_settings.get_captain_role(guild_id)
        
        # If no captain role is set, anyone can request loans
        if not captain_role_id:
            return True
            
        # Check if user has admin permissions (can always request)
        if interaction.user.guild_permissions.administrator:
            return True
            
        # Check if user has the captain role
        has_role = False
        for role in interaction.user.roles:
            if str(role.id) == captain_role_id:
                has_role = True
                break
                
        if not has_role:
            # Get the role object
            captain_role = interaction.guild.get_role(int(captain_role_id))
            role_name = captain_role.name if captain_role else "Captain role"
            
            # Send message
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        f"You need the {role_name} role to request loans in this server.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"You need the {role_name} role to request loans in this server.",
                        ephemeral=True
                    )
            except Exception as e:
                logger.error(f"Error sending permission message: {e}")
                
            return False
            
        return True
        
    def _has_outstanding_loan(self, user_id, guild_id):
        """Check if a user has any outstanding loans"""
        loan_database = self.bot.loan_database
        
        # Check both active loans and pending requests
        if "loans" in loan_database and loan_database["loans"]:
            for loan in loan_database["loans"]:
                if (loan and loan.get("user_id") == user_id and 
                    loan.get("guild_id") == guild_id and
                    loan.get("status") == "active"):
                    return loan
                    
        if "loan_requests" in loan_database and loan_database["loan_requests"]:
            for request in loan_database["loan_requests"]:
                if (request and request.get("user_id") == user_id and 
                    request.get("guild_id") == guild_id and
                    request.get("status") == "pending"):
                    return request
                    
        return None
        
    async def _generate_loan_id(self):
        """Generate a unique 4-digit loan ID"""
        loan_database = self.bot.loan_database
        existing_loans = []
        
        # Collect all existing loan IDs
        if "loans" in loan_database and loan_database["loans"]:
            existing_loans.extend(loan_database["loans"])
            
        if "loan_requests" in loan_database and loan_database["loan_requests"]:
            existing_loans.extend(loan_database["loan_requests"])
            
        # Call the global function to generate ID
        return generate_loan_id(existing_loans)
    
    def _get_credit_score(self, user_id):
        """Get a user's credit score"""
        loan_database = self.bot.loan_database
        credit_scores = loan_database.get("credit_scores", {})
        return credit_scores.get(user_id, 100)  # Default to 100
    
    def _create_loan_embed(self, interaction, loan, loan_id, amount, interest_rate, interest, total_repayment, due_date, credit_score):
        """Create an embed for loan details"""
        embed = discord.Embed(
            title="🏦 Loan Approved!",
            description=f"Captain {interaction.user.display_name}, your loan has been approved!",
            color=0x0099FF
        )
        
        embed.add_field(name="Loan ID", value=f"{loan_id}", inline=True)
        embed.add_field(name="Loan Amount", value=f"{amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
        embed.add_field(name="Total Repayment", value=f"{total_repayment} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
        
        # Format the due date as a Discord timestamp
        timestamp = int(due_date.timestamp())
        embed.add_field(name="Due Date", value=f"<t:{timestamp}:F>", inline=True)
        
        embed.add_field(name="Credit Score", value=f"{credit_score}", inline=True)
        embed.add_field(name="Late Fee", value="5% of loan amount", inline=True)
        
        embed.set_footer(text=f"Use /repay {loan_id} to repay this loan")
        
        return embed
    
    def _create_repay_button_view(self, user_id, loan_id):
        """Create a view with repay button"""
        # Create repayment button
        button = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="Repay Loan",
            custom_id=f"repay_{user_id}_{loan_id}"
        )
        
        view = discord.ui.View()
        view.add_item(button)
        
        return view
        
    @app_commands.command(name="loan", description="Request a loan for your crew")
    @app_commands.describe(
        amount=f"The amount of {config.UNBELIEVABOAT['CURRENCY_NAME']} to borrow",
        days="Number of days to repay the loan",
        reason="Reason for requesting the loan"
    )
    async def loan(self, interaction: discord.Interaction, amount: int, days: int = 7, reason: str = ""):
        """Command to request a loan from the server administrators"""
        try:
            # Check if interaction is already responded to
            if interaction.response.is_done():
                logger.warning("Interaction already acknowledged in loan command, using followup instead")
                send_message = interaction.followup.send
            else:
                # Defer the reply first to prevent interaction timeout
                try:
                    await interaction.response.defer(ephemeral=True)
                    send_message = interaction.followup.send
                except Exception as defer_error:
                    logger.warning(f"Error deferring response in loan command: {defer_error}")
                    # If we get here, the interaction was already acknowledged
                    send_message = interaction.followup.send
            
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id)
            
            # Check if user is a captain or has necessary permissions
            can_request = await self._check_can_request_loan(interaction)
            
            if not can_request:
                # Skip the message since it's handled in _check_can_request_loan
                return
            
            max_loan_amount = server_settings.get_max_loan_amount(guild_id)
            
            # Check if amount is valid
            if amount <= 0:
                return await send_message(
                    f"Loan amount must be greater than 0 {config.UNBELIEVABOAT['CURRENCY_NAME']}.",
                    ephemeral=True
                )
            
            if amount > max_loan_amount:
                return await send_message(
                    f"You can't request more than {max_loan_amount:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}.",
                    ephemeral=True
                )
            
            # Check if days is valid
            max_days = server_settings.get_max_repayment_days(guild_id)
            
            if days <= 0:
                return await send_message(
                    "Repayment days must be greater than 0.",
                    ephemeral=True
                )
                
            if days > max_days:
                return await send_message(
                    f"You can't set repayment longer than {max_days} days.",
                    ephemeral=True
                )
            
            # Check if user has outstanding loans that are not paid
            outstanding_loan = self._has_outstanding_loan(user_id, guild_id)
            
            if outstanding_loan:
                loan_id = outstanding_loan.get("id", "unknown")
                loan_amount = outstanding_loan.get("amount", 0)
                
                # Create embed for outstanding loan error
                embed = discord.Embed(
                    title="❌ Outstanding Loan",
                    description="You already have an outstanding loan that needs to be repaid first.",
                    color=0xFF0000
                )
                
                embed.add_field(
                    name="Loan ID",
                    value=loan_id,
                    inline=True
                )
                
                embed.add_field(
                    name="Amount",
                    value=f"{loan_amount:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
                    inline=True
                )
                
                embed.add_field(
                    name="How to repay",
                    value=f"Use `/repay {loan_id}` to repay your existing loan first.",
                    inline=False
                )
                
                return await send_message(
                    embed=embed,
                    ephemeral=True
                )
            
            # Generate a unique loan ID (4-digit number)
            loan_id = await self._generate_loan_id()
            
            # Calculate due date
            due_date = datetime.datetime.now() + datetime.timedelta(days=days)
            
            # No interest calculation
            interest = 0
            total_repayment = amount
            
            # Store the loan request in the database
            loan_request = {
                "id": loan_id,
                "user_id": user_id,
                "user_name": str(interaction.user),
                "guild_id": guild_id,
                "guild_name": str(interaction.guild.name) if interaction.guild else "Unknown",
                "amount": amount,
                "interest": interest,
                "total_repayment": total_repayment,
                "days": days,
                "reason": reason if reason else "No reason provided",
                "status": "pending",
                "request_date": datetime.datetime.now(),
                "due_date": due_date
            }
            
            self.bot.loan_database.setdefault("loan_requests", []).append(loan_request)
            
            # Get admin channel where to send the loan request
            admin_channel_id = server_settings.get_admin_channel(guild_id)
            
            # Send loan request to admin channel if configured
            if admin_channel_id:
                admin_channel = self.bot.get_channel(int(admin_channel_id))
                
                if admin_channel:
                    # Create embed for loan request
                    embed = discord.Embed(
                        title="🏦 Loan Request",
                        description=f"{interaction.user.mention} has requested a loan.",
                        color=0x0099FF,
                        timestamp=datetime.datetime.now()
                    )
                    
                    embed.add_field(
                        name="Loan ID",
                        value=loan_id,
                        inline=True
                    )
                    
                    embed.add_field(
                        name="User",
                        value=f"{interaction.user.mention} (ID: {user_id})",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="Amount Requested",
                        value=f"{amount:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="Total Repayment",
                        value=f"{total_repayment:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="Repayment Period",
                        value=f"{days} days (Due: <t:{int(due_date.timestamp())}:R>)",
                        inline=True
                    )
                    
                    # Get user's credit score
                    credit_score = self._get_credit_score(user_id)
                    embed.add_field(
                        name="Credit Score",
                        value=f"{credit_score}",
                        inline=True
                    )
                    
                    # Create view with approve/deny buttons
                    view = discord.ui.View(timeout=None)  # Buttons don't expire
                    
                    # Approve button
                    approve_button = discord.ui.Button(
                        style=discord.ButtonStyle.success,
                        label="Approve Loan",
                        custom_id=f"approve_loan_{loan_id}"
                    )
                    
                    # Deny button
                    deny_button = discord.ui.Button(
                        style=discord.ButtonStyle.danger,
                        label="Deny Loan",
                        custom_id=f"deny_loan_{loan_id}"
                    )
                    
                    view.add_item(approve_button)
                    view.add_item(deny_button)
                    
                    # Get approval roles
                    approval_role_ids = server_settings.get_approval_roles(guild_id)
                    
                    # Create role mentions for the approval roles
                    mention_text = ""
                    if approval_role_ids:
                        role_mentions = []
                        for role_id in approval_role_ids:
                            role = interaction.guild.get_role(int(role_id))
                            if role:
                                role_mentions.append(role.mention)
                        
                        if role_mentions:
                            mention_text = " ".join(role_mentions)
                    
                    # Send the embed with approve/deny buttons
                    await admin_channel.send(
                        content=f"New loan request from {interaction.user.mention}! {mention_text}",
                        embed=embed,
                        view=view
                    )
                    
                    # Respond to the user
                    user_embed = discord.Embed(
                        title="✅ Loan Request Submitted",
                        description="Your loan request has been submitted successfully!",
                        color=0x00FF00
                    )
                    
                    user_embed.add_field(
                        name="Loan ID",
                        value=loan_id,
                        inline=True
                    )
                    
                    user_embed.add_field(
                        name="Amount",
                        value=f"{amount:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
                        inline=True
                    )
                    
                    user_embed.add_field(
                        name="Total to Repay",
                        value=f"{total_repayment:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
                        inline=True
                    )
                    
                    user_embed.add_field(
                        name="Repayment Period",
                        value=f"{days} days (Due: <t:{int(due_date.timestamp())}:R>)",
                        inline=True
                    )
                    
                    user_embed.add_field(
                        name="Status",
                        value="Pending approval by administrators",
                        inline=False
                    )
                    
                    await send_message(
                        embed=user_embed
                    )
                else:
                    # Admin channel not found, but ID was configured
                    logger.warning(f"Admin channel {admin_channel_id} not found in guild {guild_id}")
                    
                    await send_message(
                        "Your loan request was submitted, but the admin channel for reviews could not be found. Please contact an administrator.",
                        ephemeral=True
                    )
            else:
                # No admin channel configured
                logger.warning(f"No admin channel configured for guild {guild_id}")
                
                await send_message(
                    "The loan system is not fully configured in this server. Please ask an administrator to run `/setup_loans` first.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error in loan command: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Check if we can still respond
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "There was an error processing your loan request. Please try again or contact an admin.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "There was an error processing your loan request. Please try again or contact an admin.",
                        ephemeral=True
                    )
            except Exception as e2:
                logger.error(f"Error sending error message: {e2}")
                pass

    @app_commands.command(name="loanrequests", description="View all pending loan requests (Admin only)")
    @app_commands.describe(
        ping_roles="Whether to ping approval roles (default: False)"
    )
    async def loanrequests(self, interaction: discord.Interaction, ping_roles: bool = False):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You don't have permission to view loan requests. This command is for administrators only.",
                ephemeral=True
            )
        
        await interaction.response.defer()
        
        # Get loan database
        loan_database = self.bot.loan_database
        
        # Get pending requests
        pending_requests = []
        if "loan_requests" in loan_database and loan_database["loan_requests"]:
            # Only include requests for the current guild
            guild_id = str(interaction.guild.id)
            pending_requests = [
                loan for loan in loan_database["loan_requests"] 
                if loan.get("status") == "pending" and loan.get("guild_id") == guild_id
            ]
        
        if not pending_requests:
            return await interaction.followup.send(
                "There are no pending loan requests at this time."
            )
        
        # Get approval roles to ping if needed
        ping_content = ""
        if ping_roles:
            guild_id = str(interaction.guild.id)
            approval_roles = server_settings.get_approval_roles(guild_id)
            role_mentions = []
            
            for role_id in approval_roles:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    role_mentions.append(role.mention)
            
            if role_mentions:
                ping_content = " ".join(role_mentions) + "\n"
        
        # Create embed
        embed = discord.Embed(
            title="🏦 Pending Loan Requests",
            description=f"There are {len(pending_requests)} pending loan requests.",
            color=0x0099FF
        )
        
        # Add fields for each request
        for request in pending_requests:
            loan_id = request.get("id", "Unknown")
            user_id = request.get("user_id", "Unknown")
            amount = request.get("amount", 0)
            days = request.get("days", 0)
            request_date = request.get("request_date", datetime.datetime.now())
            
            # Try to get username
            try:
                user = await self.bot.fetch_user(int(user_id))
                user_display = f"{user.name} ({user_id})"
            except:
                user_display = f"Unknown User ({user_id})"
            
            # Format timestamp
            timestamp = int(request_date.timestamp())
            
            field_value = (
                f"**Requested By:** {user_display}\n"
                f"**Amount:** {amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}\n"
                f"**Duration:** {days} days\n"
                f"**Requested:** <t:{timestamp}:R>\n\n"
                f"Use `/approveloan {loan_id}` to approve or `/denyloan {loan_id}` to deny."
            )
            
            embed.add_field(
                name=f"Request #{loan_id}",
                value=field_value,
                inline=False
            )
        
        # Create view with buttons
        view = discord.ui.View()
        
        for request in pending_requests[:5]:  # Limit to 5 to avoid too many buttons
            loan_id = request.get("id", "Unknown")
            
            # Add approve button
            approve_button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=f"Approve #{loan_id}",
                custom_id=f"approve_loan_{loan_id}"
            )
            view.add_item(approve_button)
            
            # Add deny button
            deny_button = discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label=f"Deny #{loan_id}",
                custom_id=f"deny_loan_{loan_id}"
            )
            view.add_item(deny_button)
        
        # Send response
        await interaction.followup.send(
            content=ping_content if ping_content else None,
            embed=embed, 
            view=view
        )

    @app_commands.command(name="approveloan", description="Approve a pending loan request (Admin only)")
    @app_commands.describe(
        loan_id="The ID of the loan request to approve"
    )
    async def approveloan(self, interaction: discord.Interaction, loan_id: str):
        try:
            # Check if the user has admin permissions or the approval role
            guild_id = str(interaction.guild.id)
            approval_roles = server_settings.get_approval_roles(guild_id)
            
            # Check if user has admin permissions or is in approval roles
            has_permission = interaction.user.guild_permissions.administrator
            
            if not has_permission and approval_roles:
                for role in interaction.user.roles:
                    if str(role.id) in approval_roles:
                        has_permission = True
                        break
            
            if not has_permission:
                # Check if we can respond to the interaction
                try:
                    if interaction.response.is_done():
                        await interaction.followup.send(
                            "You don't have permission to approve loan requests. This command is for administrators and approved roles only.",
                            ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            "You don't have permission to approve loan requests. This command is for administrators and approved roles only.",
                            ephemeral=True
                        )
                except Exception as e:
                    logger.error(f"Error sending permission message: {e}")
                return
                
            # Check if interaction is already acknowledged
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=False)
            except discord.errors.HTTPException as e:
                if e.code != 40060:  # Not "interaction already acknowledged"
                    logger.error(f"Error deferring response: {e}")
                    return
            
            # Initialize manual_needed variable
            manual_needed = False
            
            # Get loan database
            loan_database = self.bot.loan_database
            
            # Find the loan request
            if "loan_requests" not in loan_database or not loan_database["loan_requests"]:
                return await interaction.followup.send(
                    f"Loan request #{loan_id} not found.",
                    ephemeral=True
                )
            
            # Find loan request index
            request_index = -1
            
            for i, request in enumerate(loan_database["loan_requests"]):
                if (request and request.get("id") == loan_id and 
                    request.get("status") == "pending" and
                    request.get("guild_id") == guild_id):
                    request_index = i
                    break
            
            if request_index == -1:
                return await interaction.followup.send(
                    f"Loan request #{loan_id} not found or already processed.",
                    ephemeral=True
                )
            
            # Get the request and update status
            loan_request = loan_database["loan_requests"][request_index]
            loan_request["status"] = "approved"
            loan_request["approved_by"] = str(interaction.user.id)
            loan_request["approved_date"] = datetime.datetime.now()
            
            # Create a loan based on the request
            loan = loan_request.copy()
            loan["status"] = "active"
            
            # Save the loan
            if "loans" not in loan_database:
                loan_database["loans"] = []
                
            loan_database["loans"].append(loan)
            
            # Log successful loan creation
            logger.info(f"Created active loan #{loan_id} for user {loan_request['user_id']} with amount {loan_request['amount']}")
            logger.info(f"Current loans in database: {len(loan_database['loans'])}")
            
            # Get user information
            user_id = loan_request["user_id"]
            try:
                user = await self.bot.fetch_user(int(user_id))
                user_name = user.name
            except Exception as e:
                logger.error(f"Error fetching user: {e}")
                user_name = f"User {user_id}"
            
            # Create admin response embed
            admin_embed = discord.Embed(
                title="✅ Loan Request Approved",
                description=f"You have approved the loan request #{loan_id} for {user_name}.",
                color=0x00FF00
            )
            
            admin_embed.add_field(name="Loan ID", value=loan_id, inline=True)
            admin_embed.add_field(name="Amount", value=f"{loan_request['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
            admin_embed.add_field(name="Duration", value=f"{loan_request['days']} days", inline=True)
            
            # Send admin confirmation
            try:
                await interaction.followup.send(embed=admin_embed)
            except Exception as e:
                logger.error(f"Error sending admin confirmation: {e}")
            
            # Process UnbelievaBoat integration if enabled
            if config.UNBELIEVABOAT["ENABLED"] and unbelievaboat:
                try:
                    # Ensure guild_id is a string
                    guild_id_str = str(guild_id)
                    user_id_str = str(user_id)
                    
                    logger.info(f"Attempting to add currency for loan #{loan_id} to user {user_id_str} in guild {guild_id_str}")
                    
                    # Try the API call
                    result = await unbelievaboat.add_currency(
                        guild_id_str,
                        user_id_str,
                        loan_request["amount"],
                        f"Loan #{loan_id} - {loan_request['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']} with {loan_request['interest']} interest due in {loan_request['days']} days"
                    )
                    
                    if result:
                        # Update loan with transaction info
                        loan["unbelievaboat"] = {
                            "transaction_processed": True,
                            "balance": result["cash"],
                            "transaction_time": datetime.datetime.now().isoformat()
                        }
                        logger.info(f"Successfully added {loan_request['amount']} currency to user {user_id_str}")
                        
                        # Notify admin of success
                        try:
                            await interaction.followup.send(
                                f"✅ API Success: Added {loan_request['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']} to {user_name}'s account.",
                                ephemeral=True
                            )
                        except Exception as e:
                            logger.error(f"Error sending API success message: {e}")
                    else:
                        logger.error(f"UnbelievaBoat API returned None for add_currency call. Guild ID: {guild_id_str}, User ID: {user_id_str}, Amount: {loan_request['amount']}")
                        
                        # Fall back to manual mode if API fails
                        loan["unbelievaboat"] = {
                            "transaction_processed": False,
                            "error": "API returned None"
                        }
                        
                        # Notify admin of failure and provide manual instructions
                        try:
                            await interaction.followup.send(
                                f"⚠️ API Error: Failed to add currency through API. Please use manual command: `{config.UNBELIEVABOAT['COMMANDS']['PAY']} {user_id_str} {loan_request['amount']} Loan #{loan_id}`",
                                ephemeral=True
                            )
                        except Exception as e:
                            logger.error(f"Error sending API failure message: {e}")
                        
                        # Enable manual mode for this transaction
                        manual_needed = True
                except Exception as error:
                    logger.error(f"UnbelievaBoat API error during loan approval: {str(error)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    
                    # Fall back to manual mode on exception
                    loan["unbelievaboat"] = {
                        "transaction_processed": False,
                        "error": str(error)
                    }
                    
                    # Notify admin of failure
                    try:
                        await interaction.followup.send(
                            f"⚠️ API Error: {str(error)}. Please add currency manually.",
                            ephemeral=True
                        )
                    except Exception as e:
                        logger.error(f"Error sending API error message: {e}")
                    
                    # Enable manual mode for this transaction
                    manual_needed = True
            else:
                # API not enabled, use manual mode
                manual_needed = True
            
            # Try to notify the user
            try:
                # Create user notification embed
                user_embed = self._create_loan_embed(
                    interaction, 
                    loan, 
                    loan_id, 
                    loan_request["amount"], 
                    0.1,  # interest rate 
                    loan_request["interest"], 
                    loan_request["total_repayment"], 
                    loan_request["due_date"],
                    loan_database.get("credit_scores", {}).get(user_id, 100)
                )
                
                # Create repayment button
                view = self._create_repay_button_view(user_id, loan_id)
                
                # Try to DM the user
                user_notified = False
                try:
                    user_obj = await self.bot.fetch_user(int(user_id))
                    await user_obj.send(
                        content=f"Your loan request #{loan_id} has been approved by an administrator!",
                        embed=user_embed,
                        view=view
                    )
                    user_notified = True
                except Exception as dm_error:
                    logger.error(f"Failed to DM user: {dm_error}")
                    # If DM fails, try to find a channel to send it in
                    try:
                        channel = interaction.channel
                        if channel:
                            await channel.send(
                                content=f"<@{user_id}>, your loan request #{loan_id} has been approved!",
                                embed=user_embed,
                                view=view
                            )
                            user_notified = True
                    except Exception as channel_error:
                        logger.error(f"Failed to notify in channel: {channel_error}")
                
                # If manual mode is needed, provide instructions
                if manual_needed and manual_integration and user_notified:
                    try:
                        instructions_embed = manual_integration.format_receive_loan_instructions(
                            loan,
                            user_obj if 'user_obj' in locals() else None,
                            interaction.guild
                        )
                        
                        try:
                            if 'user_obj' in locals() and user_obj:
                                await user_obj.send(
                                    content="Here's how to receive your loan:",
                                    embed=instructions_embed
                                )
                            else:
                                channel = interaction.channel
                                if channel:
                                    await channel.send(
                                        content=f"<@{user_id}>, here's how to receive your loan:",
                                        embed=instructions_embed
                                    )
                        except Exception as send_error:
                            logger.error(f"Error sending manual instructions: {send_error}")
                    except Exception as format_error:
                        logger.error(f"Error formatting manual instructions: {format_error}")
            
            except Exception as e:
                logger.error(f"Error notifying user of loan approval: {e}")
                try:
                    await interaction.followup.send(
                        f"The loan was approved, but there was an error notifying the user: {str(e)}",
                        ephemeral=True
                    )
                except Exception as e2:
                    logger.error(f"Error sending error notification: {e2}")
        except Exception as e:
            logger.error(f"Error in approveloan command: {e}")
            import traceback
            logger.error(traceback.format_exc())
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        f"There was an error processing the loan approval: {str(e)}",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"There was an error processing the loan approval: {str(e)}",
                        ephemeral=True
                    )
            except Exception as e2:
                logger.error(f"Error sending error message: {e2}")

    @app_commands.command(name="denyloan", description="Deny a pending loan request (Admin only)")
    @app_commands.describe(
        loan_id="The ID of the loan request to deny",
        reason="The reason for denying the loan (optional)"
    )
    async def denyloan(self, interaction: discord.Interaction, loan_id: str, reason: str = None):
        # Check if the user has admin permissions or the approval role
        guild_id = str(interaction.guild.id)
        approval_roles = server_settings.get_approval_roles(guild_id)
        
        # Check if user has admin permissions or is in approval roles
        has_permission = interaction.user.guild_permissions.administrator
        
        if not has_permission and approval_roles:
            for role in interaction.user.roles:
                if str(role.id) in approval_roles:
                    has_permission = True
                    break
        
        if not has_permission:
            return await interaction.response.send_message(
                "You don't have permission to deny loan requests. This command is for administrators and approved roles only.",
                ephemeral=True
            )
            
        await interaction.response.defer()
        
        # Get loan database
        loan_database = self.bot.loan_database
        
        # Find the loan request
        if "loan_requests" not in loan_database or not loan_database["loan_requests"]:
            return await interaction.followup.send(
                f"Loan request #{loan_id} not found.",
                ephemeral=True
            )
        
        # Find loan request index
        request_index = -1
        guild_id = str(interaction.guild.id)
        
        for i, request in enumerate(loan_database["loan_requests"]):
            if (request and request.get("id") == loan_id and 
                request.get("status") == "pending" and
                request.get("guild_id") == guild_id):
                request_index = i
                break
        
        if request_index == -1:
            return await interaction.followup.send(
                f"Loan request #{loan_id} not found or already processed.",
                ephemeral=True
            )
        
        # Get the request and update status
        loan_request = loan_database["loan_requests"][request_index]
        loan_request["status"] = "denied"
        loan_request["denied_by"] = str(interaction.user.id)
        loan_request["denied_date"] = datetime.datetime.now()
        if reason:
            loan_request["denial_reason"] = reason
        
        # Get user information
        user_id = loan_request["user_id"]
        try:
            user = await self.bot.fetch_user(int(user_id))
            user_name = user.name
        except:
            user_name = f"User {user_id}"
        
        # Create admin response embed
        admin_embed = discord.Embed(
            title="❌ Loan Request Denied",
            description=f"You have denied the loan request #{loan_id} for {user_name}.",
            color=0xFF0000
        )
        
        admin_embed.add_field(name="Loan ID", value=loan_id, inline=True)
        admin_embed.add_field(name="Amount", value=f"{loan_request['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
        admin_embed.add_field(name="Duration", value=f"{loan_request['days']} days", inline=True)
        if reason:
            admin_embed.add_field(name="Reason", value=reason, inline=False)
        
        # Send admin confirmation
        await interaction.followup.send(embed=admin_embed)
        
        # Try to notify the user
        try:
            # Create user notification embed
            user_embed = discord.Embed(
                title="❌ Loan Request Denied",
                description=f"Your loan request #{loan_id} has been denied by an administrator.",
                color=0xFF0000
            )
            
            user_embed.add_field(name="Amount", value=f"{loan_request['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
            user_embed.add_field(name="Duration", value=f"{loan_request['days']} days", inline=True)
            if reason:
                user_embed.add_field(name="Reason", value=reason, inline=False)
            
            # Try to DM the user
            try:
                user_obj = await self.bot.fetch_user(int(user_id))
                await user_obj.send(embed=user_embed)
            except:
                # If DM fails, try to find a channel to send it in
                channel = interaction.channel
                await channel.send(
                    content=f"<@{user_id}>, your loan request #{loan_id} has been denied.",
                    embed=user_embed
                )
            
        except Exception as e:
            print(f"Error notifying user of loan denial: {e}")
            await interaction.followup.send(
                f"The loan was denied, but there was an error notifying the user: {str(e)}",
                ephemeral=True
            )
            
    # Handle loan approval/denial buttons
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        try:
            # Skip if not a component interaction
            if not interaction.type == discord.InteractionType.component:
                return
                
            # Ensure data exists with a custom_id
            if not hasattr(interaction, 'data') or not interaction.data:
                return
                
            # Safely get the custom_id
            custom_id = interaction.data.get("custom_id", "")
            if not custom_id:
                return
            
            # Handle loan approval button
            if custom_id.startswith("approve_loan_"):
                loan_id = custom_id.replace("approve_loan_", "")
                
                # Check permissions
                if not interaction.user.guild_permissions.administrator:
                    # Check if user has an approval role
                    guild_id = str(interaction.guild.id)
                    approval_roles = server_settings.get_approval_roles(guild_id)
                    
                    has_approval_role = False
                    for role in interaction.user.roles:
                        if str(role.id) in approval_roles:
                            has_approval_role = True
                            break
            
                    if not has_approval_role:
                        try:
                            await interaction.response.send_message(
                                "You don't have permission to approve loan requests. Only admins or users with an approval role can do this.",
                                ephemeral=True
                            )
                        except Exception as e:
                            logger.error(f"Error sending permission message: {e}")
                            if hasattr(interaction, 'followup'):
                                try:
                                    await interaction.followup.send(
                                        "You don't have permission to approve loan requests. Only admins or users with an approval role can do this.",
                                        ephemeral=True
                                    )
                                except Exception as e2:
                                    logger.error(f"Error sending followup message: {e2}")
                        return
                
                # Try to handle with approveloan method
                try:
                    # Only try to acknowledge the interaction if it hasn't been done already
                    try:
                        if not interaction.response.is_done():
                            await interaction.response.defer(ephemeral=True)
                            logger.info(f"Successfully deferred interaction for approve_loan_{loan_id}")
                    except Exception as defer_error:
                        logger.warning(f"Could not defer interaction: {defer_error}")
                        # Continue processing anyway - it's probably already acknowledged
                    
                    # Process the loan approval
                    logger.info(f"Processing loan approval for loan_id: {loan_id}")
                    
                    # Get loan database
                    loan_database = self.bot.loan_database
                    
                    # Find the loan request
                    if "loan_requests" not in loan_database or not loan_database["loan_requests"]:
                        await interaction.followup.send(
                            f"Loan request #{loan_id} not found.",
                            ephemeral=True
                        )
                        return
                    
                    # Find loan request index
                    request_index = -1
                    guild_id = str(interaction.guild.id)
                    
                    for i, request in enumerate(loan_database["loan_requests"]):
                        if (request and request.get("id") == loan_id and 
                            request.get("status") == "pending" and
                            request.get("guild_id") == guild_id):
                            request_index = i
                            break
                    
                    if request_index == -1:
                        await interaction.followup.send(
                            f"Loan request #{loan_id} not found or already processed.",
                            ephemeral=True
                        )
                        return
                    
                    # Get the request and update status
                    loan_request = loan_database["loan_requests"][request_index]
                    loan_request["status"] = "approved"
                    loan_request["approved_by"] = str(interaction.user.id)
                    loan_request["approved_date"] = datetime.datetime.now()
                    
                    # Create a loan based on the request
                    loan = loan_request.copy()
                    loan["status"] = "active"
                    
                    # Save the loan
                    if "loans" not in loan_database:
                        loan_database["loans"] = []
                        
                    loan_database["loans"].append(loan)
                    
                    # Log successful loan creation
                    logger.info(f"Created active loan #{loan_id} for user {loan_request['user_id']} with amount {loan_request['amount']}")
                    
                    # Get user information
                    user_id = loan_request["user_id"]
                    try:
                        user = await self.bot.fetch_user(int(user_id))
                        user_name = user.name
                    except:
                        user_name = f"User {user_id}"
                    
                    # Create admin response embed
                    admin_embed = discord.Embed(
                        title="✅ Loan Request Approved",
                        description=f"You have approved the loan request #{loan_id} for {user_name}.",
                        color=0x00FF00
                    )
                    
                    admin_embed.add_field(name="Loan ID", value=loan_id, inline=True)
                    admin_embed.add_field(name="Amount", value=f"{loan_request['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
                    admin_embed.add_field(name="Duration", value=f"{loan_request['days']} days", inline=True)
                    
                    # Send admin confirmation
                    await interaction.followup.send(embed=admin_embed)
                    
                    # Try to notify the user
                    try:
                        # Create user notification embed
                        user_embed = self._create_loan_embed(
                            interaction, 
                            loan, 
                            loan_id, 
                            loan_request["amount"], 
                            0.1,  # interest rate 
                            loan_request["interest"], 
                            loan_request["total_repayment"], 
                            loan_request["due_date"],
                            loan_database.get("credit_scores", {}).get(user_id, 100)
                        )
                        
                        # Create repayment button
                        view = self._create_repay_button_view(user_id, loan_id)
                        
                        # Try to DM the user
                        try:
                            user_obj = await self.bot.fetch_user(int(user_id))
                            await user_obj.send(
                                content=f"Your loan request #{loan_id} has been approved by an administrator!",
                                embed=user_embed,
                                view=view
                            )
                        except:
                            # If DM fails, try to find a channel to send it in
                            channel = interaction.channel
                            await channel.send(
                                content=f"<@{user_id}>, your loan request #{loan_id} has been approved!",
                                embed=user_embed,
                                view=view
                            )
                        
                        # Process currency through UnbelievaBoat if enabled
                        if config.UNBELIEVABOAT["ENABLED"] and unbelievaboat:
                            try:
                                guild_id_str = str(guild_id)
                                user_id_str = str(user_id)
                                
                                result = await unbelievaboat.add_currency(
                                    guild_id_str,
                                    user_id_str,
                                    loan_request["amount"],
                                    f"Loan #{loan_id} - {loan_request['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']}"
                                )
                                
                                if result:
                                    # Update loan with transaction info
                                    loan["unbelievaboat"] = {
                                        "transaction_processed": True,
                                        "balance": result["cash"],
                                        "transaction_time": datetime.datetime.now().isoformat()
                                    }
                                    
                                    # Notify admin of success
                                    await interaction.followup.send(
                                        f"✅ API Success: Added {loan_request['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']} to {user_name}'s account.",
                                        ephemeral=True
                                    )
                                else:
                                    # Fall back to manual mode with instructions
                                    await interaction.followup.send(
                                        f"⚠️ API Error: Failed to add currency automatically. Please use manual command: `{config.UNBELIEVABOAT['COMMANDS']['PAY']} {user_id} {loan_request['amount']} Loan #{loan_id}`",
                                        ephemeral=True
                                    )
                            except Exception as e:
                                logger.error(f"UnbelievaBoat API error: {e}")
                                
                                # Provide manual instructions
                                await interaction.followup.send(
                                    f"⚠️ API Error: {str(e)}. Please add currency manually using: `{config.UNBELIEVABOAT['COMMANDS']['PAY']} {user_id} {loan_request['amount']} Loan #{loan_id}`",
                                    ephemeral=True
                                )
                        
                    except Exception as e:
                        logger.error(f"Error notifying user: {e}")
                        await interaction.followup.send(
                            f"Loan approved, but there was an error notifying the user: {str(e)}",
                            ephemeral=True
                        )
                        
                except Exception as e:
                    logger.error(f"Error processing loan approval: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    
                    try:
                        await interaction.followup.send(
                            f"Error approving loan: {str(e)}",
                            ephemeral=True
                        )
                    except Exception as e2:
                        logger.error(f"Failed to send error message: {e2}")
            
            # Handle loan denial button
            elif custom_id.startswith("deny_loan_"):
                loan_id = custom_id.replace("deny_loan_", "")
                
                # Check permissions
                if not interaction.user.guild_permissions.administrator:
                    # Check if user has an approval role
                    guild_id = str(interaction.guild.id)
                    approval_roles = server_settings.get_approval_roles(guild_id)
                    
                    has_approval_role = False
                    for role in interaction.user.roles:
                        if str(role.id) in approval_roles:
                            has_approval_role = True
                            break
            
                    if not has_approval_role:
                        try:
                            await interaction.response.send_message(
                                "You don't have permission to deny loan requests. Only admins or users with an approval role can do this.",
                                ephemeral=True
                            )
                        except Exception as e:
                            logger.error(f"Error sending permission message: {e}")
                        return
            
                # Create a modal for denial reason
                modal = discord.ui.Modal(title=f"Deny Loan #{loan_id}")
            
                # Add reason input
                reason_input = discord.ui.TextInput(
                    label="Reason for denial",
                    placeholder="Enter the reason for denying this loan request",
                    required=True,
                    style=discord.TextStyle.paragraph
                )
                
                modal.add_item(reason_input)
                
                # Define callback for modal submission
                async def modal_callback(modal_interaction):
                    try:
                        reason = reason_input.value
                        await self.denyloan(modal_interaction, loan_id, reason)
                    except Exception as e:
                        logger.error(f"Error in deny loan modal: {e}")
                        try:
                            if modal_interaction.response.is_done():
                                await modal_interaction.followup.send(
                                    f"Error denying loan: {str(e)}",
                                    ephemeral=True
                                )
                            else:
                                await modal_interaction.response.send_message(
                                    f"Error denying loan: {str(e)}",
                                    ephemeral=True
                                )
                        except Exception as e2:
                            logger.error(f"Error sending error message: {e2}")
                
                modal.on_submit = modal_callback
                
                try:
                    await interaction.response.send_modal(modal)
                except Exception as e:
                    logger.error(f"Error sending modal: {e}")
                    try:
                        if interaction.response.is_done():
                            await interaction.followup.send(
                                f"Error showing denial reason form: {str(e)}",
                                ephemeral=True
                            )
                        else:
                            await interaction.response.send_message(
                                f"Error showing denial reason form: {str(e)}",
                                ephemeral=True
                            )
                    except Exception as e2:
                        logger.error(f"Error sending error message: {e2}")
        except Exception as e:
            logger.error(f"Error in loan button handler: {e}")
            import traceback
            logger.error(traceback.format_exc())


async def setup(bot):
    await bot.add_cog(LoanCommand(bot)) 