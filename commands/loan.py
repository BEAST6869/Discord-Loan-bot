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
        
    def _create_loan_embed(self, interaction, loan, loan_id, amount, interest_rate, interest, total_repayment, due_date, credit_score):
        """Create an embed for loan details"""
        embed = discord.Embed(
            title="🏦 Loan Approved!",
            description=f"Captain {interaction.user.display_name}, your loan has been approved!",
            color=0x0099FF
        )
        
        embed.add_field(name="Loan ID", value=f"{loan_id}", inline=True)
        embed.add_field(name="Loan Amount", value=f"{amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
        embed.add_field(name="Interest Rate", value=f"{(interest_rate * 100):.0f}%", inline=True)
        embed.add_field(name="Interest Amount", value=f"{interest} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
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
        days="Number of days to repay the loan"
    )
    async def loan(self, interaction: discord.Interaction, amount: int, days: int):
        # Check if the user has the captain role
        guild_id = str(interaction.guild.id)
        if not server_settings.check_is_captain(guild_id, interaction.user):
            # Get the captain role ID
            captain_role_id = server_settings.get_captain_role(guild_id)
            if captain_role_id:
                captain_role = interaction.guild.get_role(int(captain_role_id))
                role_mention = captain_role.mention if captain_role else f"role with ID {captain_role_id}"
                return await interaction.response.send_message(
                    f"Only members with the {role_mention} role can request loans. "
                    f"Please ask your server admin to give you this role if you are a captain.",
                    ephemeral=True
                )
            else:
                # This shouldn't happen since check_is_captain returns True when no role is set
                return await interaction.response.send_message(
                    "There was an error checking your permissions. Please ask your server admin to use "
                    "`/set_captain_role` to set up which role can request loans.",
                    ephemeral=True
                )
            
        # Get the maximum loan amount for this server
        max_loan_amount = server_settings.get_max_loan_amount(guild_id)
            
        # Validate input
        if amount < 1000:
            return await interaction.response.send_message(
                f"Loan amount must be at least 1,000 {config.UNBELIEVABOAT['CURRENCY_NAME']}.",
                ephemeral=True
            )
        
        if amount > max_loan_amount:
            return await interaction.response.send_message(
                f"Loan amount cannot exceed {max_loan_amount:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}. "
                f"This is the maximum set by the server administrator.",
                ephemeral=True
            )
        
        if days < 1 or days > 7:
            return await interaction.response.send_message(
                "Loan duration must be between 1 and 7 days.",
                ephemeral=True
            )
        
        # Defer the reply first to prevent interaction timeout
        await interaction.response.defer()
        
        print(f"Processing loan request from user: {interaction.user}")
        
        user_id = str(interaction.user.id)
        
        # Get loan database from bot
        loan_database = self.bot.loan_database
        
        # Calculate interest rate based on credit score
        credit_score = loan_database.get("credit_scores", {}).get(user_id, 100)  # Default score for new users
        
        # Set interest rate to 0% regardless of credit score
        interest_rate = 0.0  # 0% interest
        
        interest = round(amount * interest_rate)
        total_repayment = amount + interest
        
        # Calculate due date
        due_date = datetime.datetime.now() + datetime.timedelta(days=days)
        
        # Create a unique 4-digit ID for this loan
        loan_id = generate_loan_id(loan_database.get("loans", []))
        
        # Create loan request object
        loan_request = {
            "id": loan_id,
            "user_id": user_id,
            "amount": amount,
            "interest": interest,
            "total_repayment": total_repayment,
            "request_date": datetime.datetime.now(),
            "due_date": due_date,
            "status": "pending",
            "days": days,
            "guild_id": guild_id
        }
        
        # Save to database
        if "loan_requests" not in loan_database:
            loan_database["loan_requests"] = []
            
        loan_database["loan_requests"].append(loan_request)
        
        # Create embed for loan request details
        embed = discord.Embed(
            title="🏦 Loan Request Submitted",
            description=f"Captain {interaction.user.display_name}, your loan request has been submitted! An admin will review it shortly.",
            color=0x0099FF
        )
        
        embed.add_field(name="Request ID", value=f"{loan_id}", inline=True)
        embed.add_field(name="Loan Amount", value=f"{amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
        embed.add_field(name="Repayment Period", value=f"{days} days", inline=True)
        embed.add_field(name="Interest Rate", value=f"{(interest_rate * 100):.0f}%", inline=True)
        embed.add_field(name="Interest Amount", value=f"{interest} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
        embed.add_field(name="Total Repayment", value=f"{total_repayment} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
        
        # Format the due date as a Discord timestamp
        timestamp = int(due_date.timestamp())
        embed.add_field(name="Due Date (if approved)", value=f"<t:{timestamp}:F>", inline=True)
        
        embed.add_field(name="Credit Score", value=f"{credit_score}", inline=True)
        embed.add_field(name="Late Fee", value="5% of loan amount", inline=True)
        
        # Add status field
        embed.add_field(name="Status", value="⏳ Pending Admin Approval", inline=False)
        
        # Send to the user
        await interaction.followup.send(embed=embed)
        
        # Try to notify admins about the pending request
        try:
            # Try to find an admin channel first
            admin_channel_id = server_settings.get_admin_channel(guild_id)
            admin_channel = None
            
            if admin_channel_id:
                admin_channel = interaction.guild.get_channel(int(admin_channel_id))
            
            # If no admin channel is set, try to notify admins in the current channel
            if admin_channel:
                notification_channel = admin_channel
            else:
                notification_channel = interaction.channel
                
            # Get approval roles to ping
            approval_roles = server_settings.get_approval_roles(guild_id)
            role_mentions = []
            
            for role_id in approval_roles:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    role_mentions.append(role.mention)
            
            ping_text = " ".join(role_mentions) if role_mentions else ""
                
            # Create an admin notification embed
            admin_embed = discord.Embed(
                title="🔔 New Loan Request",
                description=f"A new loan request has been submitted by {interaction.user.mention}",
                color=0xFFA500  # Orange
            )
            
            admin_embed.add_field(name="Request ID", value=f"{loan_id}", inline=True)
            admin_embed.add_field(name="Amount", value=f"{amount} {config.UNBELIEVABOAT['CURRENCY_NAME']}", inline=True)
            admin_embed.add_field(name="Duration", value=f"{days} days", inline=True)
            admin_embed.add_field(name="Requested By", value=f"{interaction.user.display_name} ({interaction.user.id})", inline=False)
            
            # Create approval/denial buttons
            approve_button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label="Approve",
                custom_id=f"approve_loan_{loan_id}"
            )
            
            deny_button = discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="Deny",
                custom_id=f"deny_loan_{loan_id}"
            )
            
            view = discord.ui.View()
            view.add_item(approve_button)
            view.add_item(deny_button)
            
            # Send notification to admins
            notification_content = f"{ping_text}\nAttention: A new loan request requires approval" if ping_text else "Attention Admins: A new loan request requires your approval"
            
            await notification_channel.send(
                content=notification_content,
                embed=admin_embed,
                view=view
            )
        except Exception as e:
            print(f"Could not notify admins of loan request: {e}")
            # We don't need to inform the user about this, as their request is still saved

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
                "You don't have permission to approve loan requests. This command is for administrators and approved roles only.",
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
        
        # Process UnbelievaBoat integration if enabled
        if config.UNBELIEVABOAT["ENABLED"] and unbelievaboat:
            try:
                # Try the API call
                result = await unbelievaboat.add_currency(
                    guild_id,
                    user_id,
                    loan_request["amount"],
                    f"Loan #{loan_id} - {loan_request['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']} with {loan_request['interest']} interest due in {loan_request['days']} days"
                )
                
                if result:
                    # Update loan with transaction info
                    loan["unbelievaboat"] = {
                        "transaction_processed": True,
                        "balance": result["cash"]
                    }
                else:
                    print(f"UnbelievaBoat API returned None for add_currency call. Guild ID: {guild_id}, User ID: {user_id}, Amount: {loan_request['amount']}")
            except Exception as error:
                print(f"UnbelievaBoat API error during loan approval: {str(error)}")
                import traceback
                traceback.print_exc()
        
        # Try to notify the user
        try:
            # Create user notification embed
            user_embed = self._create_loan_embed(
                interaction, 
                loan, 
                loan_id, 
                loan_request["amount"], 
                0.0,  # interest rate 
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
            
            # If manual mode is needed, provide instructions
            if config.UNBELIEVABOAT["ENABLED"] and not loan.get("unbelievaboat") and manual_integration:
                instructions_embed = manual_integration.format_receive_loan_instructions(
                    loan,
                    user_obj,
                    interaction.guild
                )
                
                try:
                    await user_obj.send(
                        content="Here's how to receive your loan:",
                        embed=instructions_embed
                    )
                except:
                    await channel.send(
                        content=f"<@{user_id}>, here's how to receive your loan:",
                        embed=instructions_embed
                    )
            
        except Exception as e:
            print(f"Error notifying user of loan approval: {e}")
            await interaction.followup.send(
                f"The loan was approved, but there was an error notifying the user: {str(e)}",
                ephemeral=True
            )
    
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
            
    async def on_interaction(self, interaction):
        """Handle button interactions for loan requests"""
        if interaction.type != discord.InteractionType.component:
            return
            
        custom_id = interaction.data.get("custom_id", "")
        
        # Handle loan approval button
        if custom_id.startswith("approve_loan_"):
            # Check if the user has approval permissions
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
                    "You don't have permission to approve loan requests. This action is for administrators and approved roles only.",
                    ephemeral=True
                )
            
            # Extract loan ID from custom_id
            loan_id = custom_id.replace("approve_loan_", "")
            
            # Process the approval directly instead of calling the command
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
            
            # Process UnbelievaBoat integration if enabled
            if config.UNBELIEVABOAT["ENABLED"] and unbelievaboat:
                try:
                    # Try the API call
                    result = await unbelievaboat.add_currency(
                        guild_id,
                        user_id,
                        loan_request["amount"],
                        f"Loan #{loan_id} - {loan_request['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']} with {loan_request['interest']} interest due in {loan_request['days']} days"
                    )
                    
                    if result:
                        # Update loan with transaction info
                        loan["unbelievaboat"] = {
                            "transaction_processed": True,
                            "balance": result["cash"]
                        }
                    else:
                        print(f"UnbelievaBoat API returned None for add_currency call. Guild ID: {guild_id}, User ID: {user_id}, Amount: {loan_request['amount']}")
                except Exception as error:
                    print(f"UnbelievaBoat API error during loan approval: {str(error)}")
                    import traceback
                    traceback.print_exc()
            
            # Try to notify the user
            try:
                # Create user notification embed
                user_embed = self._create_loan_embed(
                    interaction, 
                    loan, 
                    loan_id, 
                    loan_request["amount"], 
                    0.0,  # interest rate 
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
                
                # If manual mode is needed, provide instructions
                if config.UNBELIEVABOAT["ENABLED"] and not loan.get("unbelievaboat") and manual_integration:
                    instructions_embed = manual_integration.format_receive_loan_instructions(
                        loan,
                        user_obj,
                        interaction.guild
                    )
                    
                    try:
                        await user_obj.send(
                            content="Here's how to receive your loan:",
                            embed=instructions_embed
                        )
                    except:
                        await channel.send(
                            content=f"<@{user_id}>, here's how to receive your loan:",
                            embed=instructions_embed
                        )
                
            except Exception as e:
                print(f"Error notifying user of loan approval: {e}")
                await interaction.followup.send(
                    f"The loan was approved, but there was an error notifying the user: {str(e)}",
                    ephemeral=True
                )
            
        # Handle loan denial button
        elif custom_id.startswith("deny_loan_"):
            # Check if the user has approval permissions
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
                    "You don't have permission to deny loan requests. This action is for administrators and approved roles only.",
                    ephemeral=True
                )
            
            # Extract loan ID from custom_id
            loan_id = custom_id.replace("deny_loan_", "")
            
            # Create a modal for denial reason
            modal = discord.ui.Modal(title="Deny Loan Request")
            
            # Add text input for reason
            reason_input = discord.ui.TextInput(
                label="Reason for denial",
                placeholder="Enter reason (optional)",
                required=False,
                max_length=200
            )
            modal.add_item(reason_input)
            
            # Define callback for modal submission
            async def modal_callback(modal_interaction):
                reason = reason_input.value if reason_input.value else None
                
                # Process the denial directly instead of calling the command
                await modal_interaction.response.defer()
                
                # Get loan database
                loan_database = self.bot.loan_database
                
                # Find the loan request
                if "loan_requests" not in loan_database or not loan_database["loan_requests"]:
                    return await modal_interaction.followup.send(
                        f"Loan request #{loan_id} not found.",
                        ephemeral=True
                    )
                
                # Find loan request index
                request_index = -1
                guild_id = str(modal_interaction.guild.id)
                
                for i, request in enumerate(loan_database["loan_requests"]):
                    if (request and request.get("id") == loan_id and 
                        request.get("status") == "pending" and
                        request.get("guild_id") == guild_id):
                        request_index = i
                        break
                
                if request_index == -1:
                    return await modal_interaction.followup.send(
                        f"Loan request #{loan_id} not found or already processed.",
                        ephemeral=True
                    )
                
                # Get the request and update status
                loan_request = loan_database["loan_requests"][request_index]
                loan_request["status"] = "denied"
                loan_request["denied_by"] = str(modal_interaction.user.id)
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
                await modal_interaction.followup.send(embed=admin_embed)
                
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
                        channel = modal_interaction.channel
                        await channel.send(
                            content=f"<@{user_id}>, your loan request #{loan_id} has been denied.",
                            embed=user_embed
                        )
                    
                except Exception as e:
                    print(f"Error notifying user of loan denial: {e}")
                    await modal_interaction.followup.send(
                        f"The loan was denied, but there was an error notifying the user: {str(e)}",
                        ephemeral=True
                    )
                
            modal.on_submit = modal_callback
            
            # Send the modal
            await interaction.response.send_modal(modal)


async def setup(bot):
    await bot.add_cog(LoanCommand(bot)) 