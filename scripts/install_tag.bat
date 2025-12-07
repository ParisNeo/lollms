@echo off
setlocal

:: Title
echo ==========================================
echo      LoLLMs Tag Installer (Windows)
echo ==========================================
echo.

:: 1. Verify Git Installation
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Git is not found in your PATH.
    echo Please install Git for Windows from https://git-scm.com/download/win and try again.
    pause
    exit /b 1
)

:: 2. Get Tag Version
set TAG=%1
if "%TAG%"=="" (
    set /p TAG="Enter the tag/version to install [default: v2.0.0]: "
)

if "%TAG%"=="" (
    set TAG=v2.0.0
)

:: 3. Clone Repository
set INSTALL_DIR=lollms_%TAG%
echo.
echo [INFO] Cloning LoLLMs (Tag: %TAG%) into folder "%INSTALL_DIR%"...
echo.

git clone --branch %TAG% --depth 1 https://github.com/ParisNeo/lollms.git %INSTALL_DIR%

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to clone repository. 
    echo Please check if the tag "%TAG%" exists and if you have an internet connection.
    pause
    exit /b 1
)

:: 4. Success & Instructions
echo.
echo ==========================================
echo [SUCCESS] Installation Complete!
echo ==========================================
echo.
echo To start LoLLMs, run the following commands:
echo.
echo    cd %INSTALL_DIR%
echo    run_windows.bat
echo.
pause