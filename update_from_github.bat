@echo off
cd /d %~dp0

title Git Pull

echo.
echo [BOT] 📥 Pulling latest code from GitHub...
git pull origin main

IF %ERRORLEVEL% EQU 0 (
    echo [BOT] ✅ Code updated!
) ELSE (
    echo [BOT] ❌ Pull failed. Check your connection.
)

pause
