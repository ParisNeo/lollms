@echo off
setlocal enabledelayedexpansion

:: ==================================================================
:: LOLLMs - Windows Runner & Installer
:: ==================================================================

set VENV_DIR=venv
set REQUIREMENTS_FILE=requirements.txt
set PYTHON_EXECUTABLE=python

:: --- 0. ARGUMENT PRE-PARSING ---
set UPDATE_ONLY=0
set IS_RESET=0
set RESET_USER=
set RESET_PASS=

:: Iterate through arguments to find our special flags
set argCount=0
for %%x in (%*) do (
    set /a argCount+=1
    if "%%x"=="--update" set UPDATE_ONLY=1
    if "%%x"=="--reset-password" (
        set IS_RESET=1
        :: We capture the next two arguments via a separate call because 
        :: batch loops don't support easy index-based access
    )
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
    :: Robustly find the user and pass
    set foundFlag=0
    for %%a in (%*) do (
        if "!foundFlag!"=="2" set RESET_PASS=%%a& set foundFlag=3
        if "!foundFlag!"=="1" set RESET_USER=%%a& set foundFlag=2
        if "%%a"=="--reset-password" set foundFlag=1
    )

    if "!RESET_USER!"=="" (
        echo [ERROR] Missing username for password reset.
        echo Usage: run_windows.bat --reset-password ^<username^> ^<new_password^>
        pause
        exit /b 1
    )
    if "!RESET_PASS!"=="" (
        echo [ERROR] Missing new password for password reset.
        echo Usage: run_windows.bat --reset-password ^<username^> ^<new_password^>
        pause
        exit /b 1
    )

    echo [INFO] Running Password Reset Tool for user: !RESET_USER!
    set PYTHONPATH=.
    python reset_password.py "!RESET_USER!" "!RESET_PASS!"
    pause
    exit /b 0
)

:: --- 4. UPDATE LOGIC ---
if "%UPDATE_ONLY%"=="1" (
    echo [INFO] Starting repository update...
    if exist ".git" (
        echo [INFO] Fetching latest updates from git...
        git fetch --all --tags
        
        :: Check if we are on a branch
        git symbol-ref -q HEAD >nul 2>nul
        if !errorlevel! equ 0 (
            echo [INFO] Updating current branch...
            git pull
        ) else (
            :: Find latest tag
            for /f "tokens=*" %%i in ('git describe --tags --abbrev^=0 2^>nul') do set LATEST_TAG=%%i
            if defined LATEST_TAG (
                echo [INFO] Updating to latest tag: !LATEST_TAG!...
                git checkout !LATEST_TAG!
            ) else (
                git pull
            )
        )
        echo [INFO] Updating dependencies...
        pip install --upgrade pip
        pip install --no-cache-dir -r %REQUIREMENTS_FILE%
        echo [SUCCESS] Update complete!
    ) else (
        echo [WARNING] Not a git repository. Cannot auto-update code.
    )
)

:: --- 5. ENVIRONMENT SETUP ---
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] Creating .env from example...
        copy .env.example .env >nul
    )
)

:: --- 6. EXECUTION ---
echo [INFO] Starting LOLLMs...
set PYTHONPATH=.
set PYTHONUNBUFFERED=1

:: Pass ALL original arguments to main.py
python main.py %*

if %errorlevel% neq 0 (
    echo.
    echo [INFO] Application exited with code %errorlevel%.
    pause
)
