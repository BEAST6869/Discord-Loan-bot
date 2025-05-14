@echo off
echo Adding Discord Loan Bot to Windows Startup...

:: Get the current directory where the script is located
set "SCRIPT_DIR=%~dp0"

:: Remove trailing backslash
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:: Create a shortcut in the Startup folder
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\CreateShortcut.vbs"
echo sLinkFile = oWS.SpecialFolders("Startup") ^& "\DiscordLoanBot.lnk" >> "%TEMP%\CreateShortcut.vbs"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%TEMP%\CreateShortcut.vbs"
echo oLink.TargetPath = "%SCRIPT_DIR%\startup_bot.bat" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.Description = "Discord Loan Bot Startup Script" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.Save >> "%TEMP%\CreateShortcut.vbs"
cscript /nologo "%TEMP%\CreateShortcut.vbs"
del "%TEMP%\CreateShortcut.vbs"

echo Startup shortcut created successfully!
echo The bot will now start automatically when Windows boots up.
pause 