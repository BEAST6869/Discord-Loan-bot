@echo off
echo Starting Discord Loan Bot...
cd %~dp0

:: Try to find Python path
for /f "tokens=*" %%a in ('where python') do (
    set PYTHON_PATH=%%a
    goto :found_python
)

for /f "tokens=*" %%a in ('where py') do (
    set PYTHON_PATH=%%a
    goto :found_python
)

echo Python not found in PATH. Using default Python location...
set PYTHON_PATH=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe

:found_python
echo Using Python at: %PYTHON_PATH%

:: Run the bot with windowless pythonw if available or hide the window with start /min
if exist %PYTHON_PATH:python.exe=pythonw.exe% (
    start "" %PYTHON_PATH:python.exe=pythonw.exe% run_bot.py
) else (
    start /min "" %PYTHON_PATH% run_bot.py
)

echo Bot started in background mode!
exit 