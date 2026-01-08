@echo off
setlocal enabledelayedexpansion

:: ==================================================================
:: LOLLMs - Windows Runner & Installer (Service Compatible)
:: ==================================================================

set VENV_DIR=venv
set REQUIREMENTS_FILE=requirements.txt
set PYTHON_EXECUTABLE=python
set UPDATE_FLAG_FILE=update_request.flag

:: --- 0. ARGUMENT PRE-PARSING ---
set UPDATE_ONLY=0
set IS_RESET=0
set RESET_USER=
set RESET_PASS=

:: Iterate through arguments to find our special flags
for %%x in (%*) do (
    if "%%x"=="--update" set UPDATE_ONLY=1
    if "%%x"=="--reset-password" set IS_RESET=1
)

:: --- 1. PRE-CHECKS ---
echo [INFO] Checking for Python installation...
where %PYTHON_EXECUTABLE% >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10 or higher.
    pause
    exit /b 1
)

:: --- 2. VENV SETUP ---
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [INFO] Virtual environment not found. Creating...
    %PYTHON_EXECUTABLE% -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    call .\%VENV_DIR%\Scripts\activate.bat
    echo [INFO] Installing dependencies...
    python -m pip install --upgrade pip
    pip install --no-cache-dir -r %REQUIREMENTS_FILE%
    echo [SUCCESS] Initial setup complete!
) else (
    call .\%VENV_DIR%\Scripts\activate.bat
)

:: --- 3. PASSWORD RESET INTERCEPT ---
if "%IS_RESET%"=="1" (
    set foundFlag=0
    for %%a in (%*) do (
        if "!foundFlag!"=="2" set RESET_PASS=%%a& set foundFlag=3
        if "!foundFlag!"=="1" set RESET_USER=%%a& set foundFlag=2
        if "%%a"=="--reset-password" set foundFlag=1
    )
    if "!RESET_USER!"=="" (
        echo [ERROR] Missing username. Usage: run_windows.bat --reset-password username newpass
        pause
        exit /b 1
    )
    echo [INFO] Running Password Reset Tool...
    set PYTHONPATH=.
    python reset_password.py "!RESET_USER!" "!RESET_PASS!"
    pause
    exit /b 0
)

:: --- 4. CLI UPDATE LOGIC ---
if "%UPDATE_ONLY%"=="1" (
    call :RunUpdate
    echo [SUCCESS] Update complete!
    exit /b 0
)

:: --- 5. CONFIG CHECK ---
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] Creating .env file...
        copy .env.example .env >nul
        echo SECRET_KEY=changeme>>.env
    )
)

:: --- 6. MAIN EXECUTION LOOP ---
:MainLoop
echo [INFO] Checking for update requests (from UI)...

if exist "%UPDATE_FLAG_FILE%" (
    echo [INFO] Update flag found. Updating system...
    call :RunUpdate
    del "%UPDATE_FLAG_FILE%"
    echo [INFO] Update finished. Restarting...
)

echo [INFO] Starting LOLLMs...
set PYTHONPATH=.
set PYTHONUNBUFFERED=1

:: Run main.py. If it exits (reboot/update), we loop back.
python main.py %*

echo [INFO] Application exited. Restarting in 2 seconds...
timeout /t 2 /nobreak >nul
goto MainLoop


:: --- SUBROUTINE: UPDATE ---
:RunUpdate
if exist ".git" (
    echo [INFO] Pulling from git...
    git pull
    echo [INFO] Updating requirements...
    pip install --no-cache-dir -r %REQUIREMENTS_FILE%
) else (
    echo [WARNING] Not a git repo. Skipping code pull.
)
exit /b 0
