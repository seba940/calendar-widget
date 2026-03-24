@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Checking for GitHub updates...

:: 1. Check Git executable path
set GIT_CMD=git
where %GIT_CMD% >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    set GIT_CMD="C:\Program Files\Git\bin\git.exe"
    if not exist %GIT_CMD% (
        echo [Error] Git is not installed or the path could not be found.
        pause
        exit /b
    )
)

:: 2. Fetch remote repository information
%GIT_CMD% fetch origin main >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [Warning] Could not connect to the server. Skipping update check.
    goto :RUN_APP
)

:: 3. Compare local and remote hashes
for /f "tokens=*" %%a in ('%GIT_CMD% rev-parse HEAD') do set LOCAL_HASH=%%a
for /f "tokens=*" %%b in ('%GIT_CMD% rev-parse origin/main') do set REMOTE_HASH=%%b

if "%LOCAL_HASH%" NEQ "%REMOTE_HASH%" (
    echo [Notice] A new update was found. Updating to the latest version...
    %GIT_CMD% pull origin main
) else (
    echo [Notice] You are on the latest version.
)

:RUN_APP
echo [2/3] Checking required libraries...
python -m pip install -r requirements.txt --quiet --no-warn-script-location

echo [3/3] Starting Calendar Widget...
start "" pythonw grid_calendar.pyw

echo Execution complete!
timeout /t 2 >nul
exit
