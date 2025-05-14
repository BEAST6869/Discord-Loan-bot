"""
Manual UnbelievaBoat Integration

This file provides helper functions for guiding users through manual
UnbelievaBoat currency transfers when direct API access is not available.
"""

import discord
import config


def format_receive_loan_instructions(loan, user, guild):
    """
    Formats a message with step-by-step instructions for receiving a loan
    :param loan: The loan object
    :param user: The Discord user object
    :param guild: The Discord guild object
    :return: Discord embed with instructions
    """
    # Find a server admin if possible
    server_admin = next((member for member in guild.members if member.guild_permissions.administrator), None)

    embed = discord.Embed(
        title="🏦 Loan Disbursement Instructions",
        description=f"To receive your {loan['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']} loan:",
        color=0x0099FF
    )
    
    admin_mention = f"<@{server_admin.id}>" if server_admin else "an admin"
    embed.add_field(
        name="1. Wait for Admin",
        value=f"Ask {admin_mention} to run this command:",
        inline=False
    )
    
    embed.add_field(
        name="Admin Command",
        value=f"```\n{config.UNBELIEVABOAT['COMMANDS']['PAY']} {user.id} {loan['amount']} Loan #{loan['id']}\n```",
        inline=False
    )
    
    due_timestamp = int(loan['due_date'].timestamp())
    embed.add_field(
        name="2. Repayment Due",
        value=f"You will need to repay {loan['total_repayment']} {config.UNBELIEVABOAT['CURRENCY_NAME']} by <t:{due_timestamp}:F>",
        inline=False
    )
    
    embed.add_field(
        name="3. To Repay",
        value=f"When ready to repay, use `/transfer {loan['id']} repay` for instructions",
        inline=False
    )
    
    embed.set_footer(text=f"Loan ID: {loan['id']}")
    
    return embed


def format_repay_loan_instructions(loan):
    """
    Formats a message with step-by-step instructions for repaying a loan
    :param loan: The loan object
    :return: Discord embed with instructions
    """
    bank_account = config.UNBELIEVABOAT["BANK_ACCOUNT"]
    
    embed = discord.Embed(
        title="💸 Loan Repayment Instructions",
        description=f"To repay your loan of {loan['total_repayment']} {config.UNBELIEVABOAT['CURRENCY_NAME']}:",
        color=0x00FF00
    )
    
    embed.add_field(
        name="1. Run This Command",
        value=f"Type this command in the channel:\n```\n{config.UNBELIEVABOAT['COMMANDS']['PAY']} {bank_account} {loan['total_repayment']} Loan #{loan['id']} repayment\n```",
        inline=False
    )
    
    embed.add_field(
        name="2. Confirm Repayment",
        value=f"After payment, use `/repay {loan['id']}` to mark the loan as repaid in our system",
        inline=False
    )
    
    embed.add_field(
        name="Payment Breakdown",
        value=f"Loan Amount: {loan['amount']} {config.UNBELIEVABOAT['CURRENCY_NAME']}\nInterest: {loan['interest']} {config.UNBELIEVABOAT['CURRENCY_NAME']}\nTotal Due: {loan['total_repayment']} {config.UNBELIEVABOAT['CURRENCY_NAME']}",
        inline=False
    )
    
    due_date_str = loan['due_date'].strftime("%B %d, %Y")
    embed.set_footer(text=f"Due by: {due_date_str}")
    
    return embed


def format_check_balance_instructions():
    """
    Formats a message with step-by-step instructions for checking balance
    :return: Discord embed with instructions
    """
    embed = discord.Embed(
        title="💰 Check Your Balance",
        description=f"To check your current {config.UNBELIEVABOAT['CURRENCY_NAME']} balance:",
        color=0x0099FF
    )
    
    embed.add_field(
        name="Run This Command",
        value=f"Type this command in the channel:\n```\n{config.UNBELIEVABOAT['COMMANDS']['BALANCE']}\n```",
        inline=False
    )
    
    return embed 