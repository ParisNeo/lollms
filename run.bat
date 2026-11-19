@echo off
setlocal enabledelayedexpansion

:: ==================================================================
:: LOLLMs - Windows Runner & Installer (standalone uv)
:: ==================================================================
:: Decision tree:
::   1) A working venv\ exists           -> activate + run. Done.
::   2) No working venv, uv found        -> use it to build venv\ + install deps.
::   3) No working venv, no uv           -> fetch a standalone uv, then (2).
::   4) No uv obtainable, system python   -> legacy venv + pip fallback.
::
:: Python version is pinned in PY_VERSION below (easy to bump).
:: `uv` is NEVER reinstalled if already available (PATH or bundled next to
:: this script). The venv/ folder layout is unchanged from previous releases.
:: ==================================================================

:: ------- PYTHON VERSION (bump for future releases) ---------------
:: Bump this single value on every release where you want a newer
:: interpreter. `uv python install` will fetch exactly this version.
:: Must be a real, released CPython version (e.g. 3.11, 3.12, 3.13).
set PY_VERSION=3.11
:: -----------------------------------------------------------------

set VENV_DIR=venv
set REQUIREMENTS_FILE=requirements.txt
set UPDATE_FLAG_FILE=update_request.flag
set UV_BOOTSTRAP_DIR=%~dp0uv_bootstrap
set UV_EXE=%~dp0uv.exe
set UV_RESOLVED=0

:: --- 0. ARGUMENT PRE-PARSING ---
set UPDATE_ONLY=0
set IS_RESET=0
set RESET_USER=
set RESET_PASS=

for %%x in (%*) do (
    if "%%x"=="--update" set UPDATE_ONLY=1
    if "%%x"=="--reset-password" set IS_RESET=1
)

:: ==================================================================
:: STEP 1 - Fast path: working venv present -> just run.
:: ==================================================================
if exist "%VENV_DIR%\Scripts\python.exe" (
    call .\%VENV_DIR%\Scripts\activate.bat
    goto :AfterSetup
)

:: ==================================================================
:: STEP 2/3 - No venv. Need uv (found or fetched) to build it.
:: ==================================================================
call :EnsureUv
if errorlevel 1 (
    echo [WARN] Could not obtain uv. Attempting legacy system-Python fallback...
    call :LegacyPipSetup
    if errorlevel 1 (
        echo [ERROR] Cannot bootstrap: install Python 3.10+ OR ensure internet access to fetch uv.
        pause
        exit /b 1
    )
    goto :AfterSetup
)

echo [INFO] Ensuring a managed Python %PY_VERSION% toolchain...
"!UV_EXE!" python install %PY_VERSION% >nul 2>nul
if errorlevel 1 (
    echo [WARN] Could not install managed Python %PY_VERSION%; uv will use any available Python.
)

echo [INFO] Creating virtual environment in "%VENV_DIR%"...
"!UV_EXE!" venv "%VENV_DIR%" --python %PY_VERSION%
if errorlevel 1 (
    echo [WARN] "%PY_VERSION%" venv creation failed; retrying with any available Python...
    "!UV_EXE!" venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [WARN] uv venv failed. Falling back to system Python + pip...
        call :LegacyPipSetup
        if errorlevel 1 (
            echo [ERROR] Failed to create the virtual environment.
            pause
            exit /b 1
        )
        goto :AfterSetup
    )
)

echo [INFO] Installing dependencies with uv...
"!UV_EXE!" pip install --python "%VENV_DIR%\Scripts\python.exe" --upgrade pip wheel setuptools
"!UV_EXE!" pip install --python "%VENV_DIR%\Scripts\python.exe" --no-cache-dir -r %REQUIREMENTS_FILE%
if errorlevel 1 (
    echo [WARN] uv dependency install failed. Retrying with pip inside venv...
    call .\%VENV_DIR%\Scripts\activate.bat
    python -m pip install --upgrade pip wheel setuptools
    pip install --no-cache-dir -r %REQUIREMENTS_FILE%
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed.
        pause
        exit /b 1
    )
)
call .\%VENV_DIR%\Scripts\activate.bat
echo [SUCCESS] Initial setup complete.

:: ==================================================================
:: STEP 4 - Optional CLI paths (reset-password / update)
:: ==================================================================
:AfterSetup

if "%IS_RESET%"=="1" (
    set foundFlag=0
    for %%a in (%*) do (
        if "!foundFlag!"=="2" set RESET_PASS=%%a& set foundFlag=3
        if "!foundFlag!"=="1" set RESET_USER=%%a& set foundFlag=2
        if "%%a"=="--reset-password" set foundFlag=1
    )
    if "!RESET_USER!"=="" (
        echo [ERROR] Missing username. Usage: run.bat --reset-password username newpass
        pause
        exit /b 1
    )
    echo [INFO] Running Password Reset Tool...
    set PYTHONPATH=.
    python reset_password.py "!RESET_USER!" "!RESET_PASS!"
    pause
    exit /b 0
)

if "%UPDATE_ONLY%"=="1" (
    call :RunUpdate
    echo [SUCCESS] Update complete!
    exit /b 0
)

:: ==================================================================
:: STEP 5 - First-run .env bootstrap
:: ==================================================================
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] Creating .env file...
        copy .env.example .env >nul
        echo [INFO] Generating secure SECRET_KEY...
        for /f "delims=" %%i in ('python -c "import secrets; print(secrets.token_urlsafe(32))"') do set SECURE_KEY=%%i
        echo SECRET_KEY=!SECURE_KEY!>>.env
    )
)

:: ==================================================================
:: STEP 6 - Main execution loop
:: ==================================================================
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

python main.py %*

echo [INFO] Application exited. Restarting in 2 seconds...
timeout /t 2 /nobreak >nul
goto MainLoop


:: ==================================================================
:: SUBROUTINES
:: ==================================================================

:EnsureUv
:: Resolve uv WITHOUT reinstalling when present.
::   1) bundled next to this script (release archive ships uv.exe — wins over PATH
::      so a shipped bundle is fully self-contained and reproducible)
::   2) PATH
::   3) download standalone exe
:: Sets UV_EXE + UV_RESOLVED. Returns errorlevel 1 on failure.
set UV_RESOLVED=0

:: 1) Bundled next to this script
if exist "%UV_EXE%" (
    echo [INFO] Using bundled uv: %UV_EXE%
    set UV_RESOLVED=1
    exit /b 0
)

:: 2) PATH
where uv >nul 2>nul
if !errorlevel! equ 0 (
    for /f "delims=" %%i in ('where uv') do (
        if !UV_RESOLVED! equ 0 (
            set UV_EXE=%%i
            set UV_RESOLVED=1
        )
    )
    if !UV_RESOLVED! equ 1 (
        echo [INFO] uv already installed: !UV_EXE!
        exit /b 0
    )
)

:: 3) Download standalone uv.exe (no Python required)
echo [INFO] uv not found. Downloading standalone uv...
if not exist "%UV_BOOTSTRAP_DIR%" mkdir "%UV_BOOTSTRAP_DIR%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue';" ^
  "$arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {'aarch64'} else {'x86_64'};" ^
  "$url = 'https://github.com/astral-sh/uv/releases/latest/download/uv-' + $arch + '-pc-windows-msvc.zip';" ^
  "$tmp = Join-Path $env:TEMP ('uv-' + [guid]::NewGuid().ToString('N') + '.zip');" ^
  "Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing;" ^
  "Expand-Archive -Path $tmp -DestinationPath '%UV_BOOTSTRAP_DIR%' -Force;" ^
  "Remove-Item $tmp -Force;" ^
  "if (Test-Path (Join-Path '%UV_BOOTSTRAP_DIR%' 'uv.exe')) { Copy-Item (Join-Path '%UV_BOOTSTRAP_DIR%' 'uv.exe') '%UV_EXE%' -Force }"
if exist "%UV_EXE%" (
    echo [INFO] uv downloaded: %UV_EXE%
    set UV_RESOLVED=1
    exit /b 0
)

:: 4) Last resort: pip install uv (requires Python)
echo [WARN] Direct uv download failed. Trying pip install uv (needs Python)...
where python >nul 2>nul
if !errorlevel! equ 0 (
    python -m pip install --upgrade uv
    where uv >nul 2>nul
    if !errorlevel! equ 0 (
        for /f "delims=" %%i in ('where uv') do (
            if !UV_RESOLVED! equ 0 (
                set UV_EXE=%%i
                set UV_RESOLVED=1
            )
        )
        if !UV_RESOLVED! equ 1 (
            echo [INFO] uv installed via pip: !UV_EXE!
            exit /b 0
        )
    )
)
exit /b 1


:LegacyPipSetup
:: System python + pip into venv\. Returns errorlevel 1 on failure.
:: NOTE: all `if errorlevel` checks below run in this subroutine's own
:: scope, invoked via `call :LegacyPipSetup` + `if errorlevel 1` at the
:: caller — no reliance on delayed expansion across parenthesized blocks.
where python >nul 2>nul
if errorlevel 1 exit /b 1
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    python -m venv %VENV_DIR%
    if errorlevel 1 exit /b 1
)
call .\%VENV_DIR%\Scripts\activate.bat
python -m pip install --upgrade pip wheel setuptools
if errorlevel 1 exit /b 1
pip install --no-cache-dir -r %REQUIREMENTS_FILE%
if errorlevel 1 exit /b 1
echo [SUCCESS] Legacy pip setup complete.
exit /b 0


:RunUpdate
if exist ".git" (
    echo [INFO] Pulling from git...
    git pull
    echo [INFO] Updating requirements...
    if exist "%VENV_DIR%\Scripts\activate.bat" call .\%VENV_DIR%\Scripts\activate.bat
    if exist "!UV_EXE!" (
        "!UV_EXE!" pip install --python "%VENV_DIR%\Scripts\python.exe" --no-cache-dir -r %REQUIREMENTS_FILE%
        if !errorlevel! neq 0 (
            echo [WARN] uv update failed. Retrying with pip...
            pip install --no-cache-dir -r %REQUIREMENTS_FILE%
        )
    ) else (
        pip install --no-cache-dir -r %REQUIREMENTS_FILE%
    )
) else (
    echo [WARN] Not a git repo. Skipping code pull.
)
exit /b 0