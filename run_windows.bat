@echo off
setlocal enabledelayedexpansion

:: ==================================================================
:: LOLLMs - Windows Runner
:: ==================================================================
:: This script installs necessary components if they are missing,
:: then starts the application server.

set VENV_DIR=venv
set REQUIREMENTS_FILE=requirements.txt
set PYTHON_EXECUTABLE=python

:: --- 1. PRE-CHECKS ---
echo [INFO] Checking for Python installation...
where %PYTHON_EXECUTABLE% >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10 or higher and ensure it's in your PATH.
    pause
    exit /b 1
)
echo [SUCCESS] Python found.

:: --- 2. SETUP OR START ---
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [INFO] Virtual environment not found. Starting setup...

    :: --- 2a. Create Virtual Environment ---
    echo [INFO] [1/2] Creating Python virtual environment...
    %PYTHON_EXECUTABLE% -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [SUCCESS] Virtual environment created.

    :: Activate
    call .\%VENV_DIR%\Scripts\activate.bat

    :: --- 2b. Install Dependencies ---
    echo [INFO] [2/2] Installing dependencies from %REQUIREMENTS_FILE%...
    pip install --no-cache-dir -r %REQUIREMENTS_FILE%
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install required packages.
        pause
        exit /b 1
    )
    echo [SUCCESS] Dependencies installed.
    echo.
    echo [SUCCESS] Setup complete!
    echo.

) else (
    echo [INFO] Virtual environment found. Activating...
    call .\%VENV_DIR%\Scripts\activate.bat
)

:: --- 3. CHECK FOR .env FILE ---
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] '.env' file not found. Creating from '.env.example'...
        copy .env.example .env >nul
        echo [SUCCESS] '.env' file created. You may want to edit it for custom configurations.
        echo.
    ) else (
        echo [WARNING] '.env' and '.env.example' files not found. The application might use default settings.
        echo.
    )
)

:: --- 4. START THE SERVER ---
echo [INFO] Setting Python Path...
set PYTHONPATH=.

set PORT_TO_USE=9642
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        set "line=%%a"
        for /f "tokens=* delims= " %%k in ("!line!") do set "trimmed_key=%%k"
        if /i "!trimmed_key!"=="SERVER_PORT" (
            set "val=%%~b"
            for /f "tokens=* delims= " %%v in ("!val!") do set "PORT_TO_USE=%%v"
        )
    )
)

echo [INFO] Starting Simplified LOLLMs Server on port !PORT_TO_USE!...
echo To stop the server, simply close this window or press Ctrl+C.
echo.

%PYTHON_EXECUTABLE% main.py

echo [INFO] Server has been stopped.
pause
exit /b 0