@echo off
set ERRORLEVEL=0

:: Check for admin privileges
net session >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Please run this script as Administrator.
    pause
    exit /b 1
)

:: Check for virtual environment
if not exist "venv" (
    echo 🔧 Creating Python Virtual Environment...
    python -m venv venv
    if %ERRORLEVEL% neq 0 (
        echo ❌ Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo ✅ Virtual environment already exists
)

:: Activate virtual environment
call venv\Scripts\activate
if %ERRORLEVEL% neq 0 (
    echo ❌ Failed to activate virtual environment.
    pause
    exit /b 1
)

:: Check for requirements.txt
if exist "requirements.txt" (
    echo 📦 Installing Python Dependencies...
    pip install --upgrade pip >nul 2>&1
    pip install -r requirements.txt >nul 2>&1
) else (
    echo ⚠️ Warning: Requirements file not found. Please run 'pip freeze > requirements.txt' to create one.
)

:: Copy config if needed
if exist "config_example.toml" and not exist "config.toml" (
    copy /y "config_example.toml" "config.toml"
)

:: Function to update TOML config (simplified)
:UPDATE_CONFIG
set /p "new_val=Enter value for %1 [%2]: "
if "%new_val%"=="" set "new_val=%2"
echo %new_val% > temp.txt
findstr /v /c:"%1 = " config.toml > temp2.txt
echo %new_val% >> temp2.txt
move /y temp2.txt config.toml >nul
del temp.txt
goto :EOF

:: Function to update raw config (simplified)
:UPDATE_CONFIG_RAW
set /p "new_val=Enter value for %1 [%2]: "
if "%new_val%"=="" set "new_val=%2"
echo %new_val% > temp.txt
findstr /v /c:"%1 = " config.toml > temp2.txt
echo %new_val% >> temp2.txt
move /y temp2.txt config.toml >nul
del temp.txt
goto :EOF

:: Function to update secure config (simplified)
:UPDATE_CONFIG_SECURE
set /p "new_val=Enter value for %1 [****]: " <nul
if "%new_val%"=="" set "new_val=CHANGE_ME_TO_A_STRONG_PASSWORD"
echo %new_val% > temp.txt
findstr /v /c:"%1 = " config.toml > temp2.txt
echo "%new_val%" >> temp2.txt
move /y temp2.txt config.toml >nul
del temp.txt
goto :EOF

:: Server settings
echo 🔧 Configure [server] Settings
call :UPDATE_CONFIG "host" "0.0.0.0"
call :UPDATE_CONFIG_RAW "port" 9642

:: App settings
echo 🔧 Configure [app_settings] Settings
call :UPDATE_CONFIG "data_dir" "data"
call :UPDATE_CONFIG "database_url" "sqlite:///./data/app_main.db"

:: Secret key generation
set /p "gen_secret=Generate new secret_key? (y/N) [N]: "
if /i "%gen_secret%" == "Y" (
    for /f "delims=" %%i in ('openssl rand -base64 32') do set "new_secret=%%i"
    echo %new_secret% > temp.txt
    findstr /v /c:"secret_key = " config.toml > temp2.txt
    echo "secret_key = %new_secret%" >> temp2.txt
    move /y temp2.txt config.toml >nul
    del temp.txt
)

:: Initial admin user
echo 🔧 Configure [initial_admin_user] Settings
call :UPDATE_CONFIG "username" "superadmin"
set /p "gen_pass=Generate secure password? (y/N) [N]: "
if /i "%gen_pass%" == "Y" (
    for /f "delims=" %%i in ('openssl rand -base64 20') do set "new_password=%%i"
    echo 🔐 Generated password: %new_password% (will be hashed in DB)
) else (
    call :UPDATE_CONFIG_SECURE "password"
)

:: Lollms client defaults
echo 🔧 Configure [lollms_client_defaults] Settings
call :UPDATE_CONFIG "binding_name" "ollama"
call :UPDATE_CONFIG "default_model_name" "phi4:latest"
call :UPDATE_CONFIG "host_address" "http://localhost:11434"
call :UPDATE_CONFIG "service_key_env_var" "OPENAI_API_KEY"

:: Safe store defaults
echo 🔧 Configure [safe_store_defaults] Settings
call :UPDATE_CONFIG_RAW "chunk_size" 512
call :UPDATE_CONFIG_RAW "chunk_overlap" 50

:: Encryption key generation
set /p "gen_encryption=Generate new encryption_key? (y/N) [N]: "
if /i "%gen_encryption%" == "Y" (
    for /f "delims=" %%i in ('openssl rand -base64 32') do set "new_enc_key=%%i"
    echo %new_enc_key% > temp.txt
    findstr /v /c:"encryption_key = " config.toml > temp2.txt
    echo "encryption_key = %new_enc_key%" >> temp2.txt
    move /y temp2.txt config.toml >nul
    del temp.txt
)

echo ✅ Installation complete!
echo Virtual environment created in venv
echo Configuration saved to config.toml

if exist "venv\Scripts\activate" (
    echo To activate the virtual environment:
    echo source ./venv/bin/activate
)

echo You can now start your application!

echo 🚀 Installation complete!
pause
