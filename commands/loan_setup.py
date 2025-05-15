import discord
from discord import app_commands
from discord.ext import commands
import sys
import os
import config

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server_settings

class LoanSetupCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="setup_loans", description="Configure loan request settings (Admin only)")
    @app_commands.describe(
        channel="The channel where loan requests will be sent"
    )
    async def setup_loans(self, interaction: discord.Interaction, channel: discord.TextChannel):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You don't have permission to use this command. Only administrators can configure loan settings.",
                ephemeral=True
            )
        
        # Defer the reply
        await interaction.response.defer(ephemeral=True)
            
        guild_id = str(interaction.guild.id)
        channel_id = str(channel.id)
        
        # Update the server settings
        success = server_settings.set_admin_channel(guild_id, channel_id)
        
        if not success:
            return await interaction.followup.send(
                "❌ There was an error setting the loan request channel. Please try again.",
                ephemeral=True
            )
        
        # Create a selection menu for approval roles
        # We'll use a select menu with available roles in the server
        roles_select = discord.ui.RoleSelect(
            placeholder="Select roles that can approve loans",
            min_values=0,
            max_values=10  # Set to a reasonable limit
        )
        
        # Create the view
        view = discord.ui.View(timeout=300)  # 5 minute timeout
        view.add_item(roles_select)
        
        # Add a submit button
        submit_button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="Save Settings",
            custom_id="save_loan_settings"
        )
        view.add_item(submit_button)
        
        # Save the original message so we can edit it
        message = await interaction.followup.send(
            f"✅ Loan request channel set to {channel.mention}. Now select which roles can approve loan requests:",
            view=view,
            ephemeral=True
        )
        
        # Define what happens when the submit button is clicked
        async def on_submit(submit_interaction):
            # Get the selected roles
            selected_roles = [str(role.id) for role in roles_select.values]
            
            # Save the roles to the server settings
            server_settings.set_approval_roles(guild_id, selected_roles)
            
            # Format the role mentions
            role_mentions = []
            for role_id in selected_roles:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    role_mentions.append(role.mention)
            
            role_text = ", ".join(role_mentions) if role_mentions else "No roles selected (Admins only)"
            
            # Update the message
            await message.edit(
                content=f"✅ Loan settings configured successfully!\n\n**Loan Request Channel:** {channel.mention}\n**Approval Roles:** {role_text}",
                view=None  # Remove the view
            )
            
            # Acknowledge the interaction
            await submit_interaction.response.defer()
            
        # Bind the button callback
        submit_button.callback = on_submit
    
    @app_commands.command(name="loan_notification_roles", description="Set roles to be pinged for loan requests (Admin only)")
    @app_commands.describe(
        roles="The roles to ping when a loan request is received (comma-separated IDs)"
    )
    async def loan_notification_roles(self, interaction: discord.Interaction, roles: str):
        """Set roles to be pinged when a loan request is submitted"""
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You don't have permission to use this command. Only administrators can configure loan settings.",
                ephemeral=True
            )
        
        guild_id = str(interaction.guild.id)
        
        # Parse the role IDs
        try:
            role_ids = [role_id.strip() for role_id in roles.split(",")]
            valid_role_ids = []
            
            # Validate role IDs
            for role_id in role_ids:
                try:
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        valid_role_ids.append(str(role.id))
                except ValueError:
                    pass
            
            # Save the roles
            server_settings.set_approval_roles(guild_id, valid_role_ids)
            
            # Format role mentions
            role_mentions = []
            for role_id in valid_role_ids:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    role_mentions.append(role.mention)
            
            role_text = ", ".join(role_mentions) if role_mentions else "No valid roles provided"
            
            return await interaction.response.send_message(
                f"✅ Loan approval roles set to: {role_text}",
                ephemeral=True
            )
        except Exception as e:
            return await interaction.response.send_message(
                f"❌ Error setting approval roles: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="view_loan_settings", description="View current loan request settings (Admin only)")
    async def view_loan_settings(self, interaction: discord.Interaction):
        """View the current loan request settings"""
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You don't have permission to use this command. Only administrators can view loan settings.",
                ephemeral=True
            )
        
        guild_id = str(interaction.guild.id)
        
        # Get the current settings
        admin_channel_id = server_settings.get_admin_channel(guild_id)
        approval_role_ids = server_settings.get_approval_roles(guild_id)
        max_loan_amount = server_settings.get_max_loan_amount(guild_id)
        captain_role_id = server_settings.get_captain_role(guild_id)
        
        # Create the embed
        embed = discord.Embed(
            title="Loan Request Settings",
            description="Current settings for loan requests in this server",
            color=0x0099FF
        )
        
        # Add channel information
        channel_text = "Not set"
        if admin_channel_id:
            channel = interaction.guild.get_channel(int(admin_channel_id))
            channel_text = channel.mention if channel else f"Unknown channel (ID: {admin_channel_id})"
        
        embed.add_field(
            name="Loan Request Channel",
            value=channel_text,
            inline=False
        )
        
        # Add approval roles information
        role_mentions = []
        for role_id in approval_role_ids:
            role = interaction.guild.get_role(int(role_id))
            if role:
                role_mentions.append(role.mention)
        
        role_text = ", ".join(role_mentions) if role_mentions else "No roles set (Admins only)"
        
        embed.add_field(
            name="Approval Roles",
            value=role_text,
            inline=False
        )
        
        # Add max loan amount
        embed.add_field(
            name="Maximum Loan Amount",
            value=f"{max_loan_amount:,}",
            inline=True
        )
        
        # Add captain role
        captain_text = "Not set (everyone can request loans)"
        if captain_role_id:
            captain_role = interaction.guild.get_role(int(captain_role_id))
            captain_text = captain_role.mention if captain_role else f"Unknown role (ID: {captain_role_id})"
        
        embed.add_field(
            name="Captain Role",
            value=captain_text,
            inline=True
        )
        
        # Send the embed
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="set_captain_role", description="Set which role is allowed to request loans")
    @app_commands.describe(
        role="The role that can request loans (captains)"
    )
    async def set_captain_role(self, interaction: discord.Interaction, role: discord.Role):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You don't have permission to use this command. This command is for administrators only.",
                ephemeral=True
            )
            
        # Save the captain role ID
        guild_id = str(interaction.guild.id)
        server_settings.set_captain_role(guild_id, str(role.id))
        
        await interaction.response.send_message(
            f"✅ The captain role has been set to {role.mention}. "
            f"Members with this role can now request loans using the `/loan` command.",
            ephemeral=True
        )

    @app_commands.command(name="set_max_loan_amount", description="Set the maximum loan amount captains can request")
    @app_commands.describe(
        amount=f"Maximum loan amount in {config.UNBELIEVABOAT['CURRENCY_NAME']}"
    )
    async def set_max_loan_amount(self, interaction: discord.Interaction, amount: int):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You don't have permission to use this command. This command is for administrators only.",
                ephemeral=True
            )
            
        # Validate amount
        if amount < 1000:
            return await interaction.response.send_message(
                f"Maximum loan amount must be at least 1,000 {config.UNBELIEVABOAT['CURRENCY_NAME']}.",
                ephemeral=True
            )
            
        # Save the max loan amount
        guild_id = str(interaction.guild.id)
        server_settings.set_max_loan_amount(guild_id, amount)
        
        await interaction.response.send_message(
            f"✅ The maximum loan amount has been set to {amount:,} {config.UNBELIEVABOAT['CURRENCY_NAME']}.",
            ephemeral=True
        )

    @app_commands.command(name="set_max_repayment_days", description="Set the maximum number of days allowed for loan repayment")
    @app_commands.describe(
        days="Maximum number of days for loan repayment (use 9999 for unlimited)"
    )
    async def set_max_repayment_days(self, interaction: discord.Interaction, days: int):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You don't have permission to use this command. This command is for administrators only.",
                ephemeral=True
            )
            
        # Validate days
        if days < 1:
            return await interaction.response.send_message(
                "Maximum repayment days must be at least 1.",
                ephemeral=True
            )
            
        # Save the max repayment days
        guild_id = str(interaction.guild.id)
        server_settings.set_max_repayment_days(guild_id, days)
        
        # Create appropriate message based on value
        if days >= 9999:
            message = "✅ The maximum repayment period has been set to unlimited days."
        else:
            message = f"✅ The maximum repayment period has been set to {days} days."
        
        await interaction.response.send_message(
            message,
            ephemeral=True
        )
    
    @app_commands.command(name="set_installment_enabled", description="Enable or disable installment payments for loans")
    @app_commands.describe(
        enabled="Whether installment payments are enabled (default: True)"
    )
    async def set_installment_enabled(self, interaction: discord.Interaction, enabled: bool = True):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You don't have permission to use this command. This command is for administrators only.",
                ephemeral=True
            )
            
        # Save the installment enabled setting
        guild_id = str(interaction.guild.id)
        server_settings.set_installment_enabled(guild_id, enabled)
        
        await interaction.response.send_message(
            f"✅ Installment payments for loans have been {'enabled' if enabled else 'disabled'}.",
            ephemeral=True
        )
    
    @app_commands.command(name="set_min_installment_percent", description="Set the minimum installment percentage for loans")
    @app_commands.describe(
        percent="Minimum percentage of loan that must be paid in each installment (1-100)"
    )
    async def set_min_installment_percent(self, interaction: discord.Interaction, percent: int):
        # Check if the user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "You don't have permission to use this command. This command is for administrators only.",
                ephemeral=True
            )
            
        # Validate percent
        if percent < 1 or percent > 100:
            return await interaction.response.send_message(
                "Minimum installment percentage must be between 1 and 100.",
                ephemeral=True
            )
            
        # Save the min installment percentage
        guild_id = str(interaction.guild.id)
        server_settings.set_min_installment_percent(guild_id, percent)
        
        await interaction.response.send_message(
            f"✅ The minimum installment percentage has been set to {percent}% of the total loan amount.",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(LoanSetupCommand(bot)) 