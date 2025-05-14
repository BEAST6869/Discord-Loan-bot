@echo off
echo Starting Discord Loan Bot watchdog...
cd /d "%~dp0"
py -3.11 run_bot.py
pause 