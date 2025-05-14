# Discord Loan Bot

A Discord bot for managing loans in One Piece themed crews, allowing captains to request loans with admin approval.

## Features

- **Loan Management**: Request, approve, and manage loans within Discord
- **Multi-Guild Support**: Works across multiple servers with separate configurations
- **Role-Based Permissions**: Restrict loan access to specific roles
- **Admin Controls**: Configure various settings like maximum loan amounts
- **Credit System**: Track user credit scores based on loan repayment history
- **UnbelievaBoat Integration**: Fully integrates with UnbelievaBoat economy
- **Automatic Restart**: Bot watchdog ensures the service stays online

## Commands

### Loan Commands
- `/loan <amount> <days>` - Request a loan for your crew
- `/repay <loan_id>` - Repay an active loan
- `/myloans` - View your active loans
- `/allloans` - View all active loans in the server (Admin only)
- `/loanstats` - View loan statistics for the server

### Loan Request Commands
- `/loanrequests` - View pending loan requests (Admin/Approval Roles)
- `/approveloan <loan_id>` - Approve a pending loan request (Admin/Approval Roles)
- `/denyloan <loan_id> <reason>` - Deny a pending loan request (Admin/Approval Roles)

### Admin Setup Commands
- `/set_captain_role <role>` - Set which role can request loans (Admin only)
- `/set_max_loan <amount>` - Set the maximum loan amount (Admin only)
- `/setup_loans <channel>` - Configure loan request channel and approval roles (Admin only)
- `/set_admin_channel <channel>` - Set where loan notifications appear (Admin only)
- `/loan_notification_roles <roles>` - Set roles to ping for loan requests (Admin only)
- `/view_loan_settings` - View loan request configuration (Admin only)
- `/view_settings` - View all server settings for the bot

## Installation

### Local Setup
1. Clone this repository
2. Install the requirements:
   ```
   pip install -r requirements.txt
   ```
3. Copy `config_template.py` to `config.py` and update with your actual tokens:
   ```
   cp config_template.py config.py
   ```
   Then edit `config.py` with your Discord token and UnbelievaBoat API key.
4. Run the bot:
   ```
   python run_bot.py
   ```

### Deployment on Render
1. Fork this repository to your GitHub account
2. Sign up for [Render](https://render.com) and connect your GitHub account
3. Click "New Web Service" and select your forked repository
4. Render will automatically detect the configuration from `render.yaml`
5. Add the following environment variables in the Render dashboard:
   - `DISCORD_TOKEN`: Your Discord bot token
   - `UNBELIEVABOAT_API_KEY`: Your UnbelievaBoat API key
   - `CLIENT_ID`: Your Discord application client ID
6. Deploy the service

## Auto-Startup Configuration

The bot includes scripts to automatically start on system boot:

### Windows
Run `add_to_startup.bat` to create a startup shortcut that will run the bot whenever Windows starts.

## Dependencies

- Python 3.8+
- discord.py
- aiohttp
- python-dotenv

## UnbelievaBoat Integration

The bot can integrate with the UnbelievaBoat economy bot in two ways:

1. **API Integration** - Direct interaction with UnbelievaBoat's API (requires API key)
2. **Manual Mode** - Guides users through manual commands to interact with UnbelievaBoat

## Database

The bot uses a simple JSON-based database stored in the `data` directory. The database is automatically backed up every 5 minutes.

## Troubleshooting

### Common Issues

- **Command not found**: Make sure you've deployed the slash commands with `python deploy_commands.py`
- **Permission errors**: Ensure the bot has proper permissions in your Discord server
- **Duplicate commands**: Run `python cleanup_commands.py` to clear all commands and then redeploy them

### Cleanup Commands

If you encounter issues with commands, you can run the cleanup script to remove all commands and start fresh:

```
python cleanup_commands.py
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- Based on the original Node.js implementation
- Uses discord.py for Discord API interaction
- Designed for One Piece themed Discord servers 