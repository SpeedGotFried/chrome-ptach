@echo off
title Launch Chrome with Remote Debugging
echo ==============================================
echo   Launching Chrome in Remote Debugging Mode   
echo ==============================================

set "PORT=9222"
set "USER_DIR=%TEMP%\chrome-debug-profile"

:: Locate chrome.exe across standard installation paths
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    set "CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe"
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    set "CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
) else if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_PATH=%LocalAppData%\Google\Chrome\Application\chrome.exe"
) else (
    echo [-] Error: Google Chrome could not be found in standard paths.
    echo Please edit this batch file and set the correct path to your chrome.exe.
    pause
    exit /b 1
)

echo [+] Launching Chrome...
echo [+] Port: %PORT%
echo [+] Profile Directory: %USER_DIR%
echo ==============================================

start "" "%CHROME_PATH%" --remote-debugging-port=%PORT% --user-data-dir="%USER_DIR%" --no-first-run --no-default-browser-check

exit /b 0
