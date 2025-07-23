@echo off
setlocal EnableDelayedExpansion

echo Starting Lollms Installation Script

:: Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating Python Virtual Environment...
    python -m venv venv

    call venv\Scripts\activate.bat

    if exist "requirements.txt" (
        echo Installing Python Dependencies...
        pip install --upgrade pip >nul 2>&1
        pip install -r requirements.txt >nul 2>&1
    ) else (
        echo Warning: requirements.txt not found.
    )
) else (
    echo Virtual environment already exists
)

:: Copy config_example.toml to config.toml if needed
if exist "config_example.toml" (
    if not exist "config.toml" (
        copy config_example.toml config.toml >nul
    )
)

:: Prompt function-like replacements
set /p host=Enter host [0.0.0.0]: 
if "!host!"=="" set host=0.0.0.0
call :update_config host "!host!"

set /p port=Enter port [9642]: 
if "!port!"=="" set port=9642
call :update_config_raw port !port!

set /p data_dir=Enter data_dir [data]: 
if "!data_dir!"=="" set data_dir=data
call :update_config data_dir "!data_dir!"

set /p db_url=Enter database_url [sqlite:///./data/app_main.db]: 
if "!db_url!"=="" set db_url=sqlite:///./data/app_main.db
call :update_config database_url "!db_url!"

set /p gen_secret=Generate new secret_key? (y/N): 
if /I "!gen_secret!"=="Y" (
    for /f %%A in ('powershell -Command "[Convert]::ToBase64String((1..32 | %% { Get-Random -Minimum 0 -Maximum 256 }))"') do set new_secret=%%A
    call :update_config secret_key "!new_secret!"
)

:: Safe store defaults
set /p chunk=Enter chunk_size [4096]: 
if "!chunk!"=="" set chunk=4096
call :update_config_raw chunk_size !chunk!

set /p overlap=Enter chunk_overlap [200]: 
if "!overlap!"=="" set overlap=200
call :update_config_raw chunk_overlap !overlap!

:: Encryption key
set /p gen_enc=Generate new encryption_key? (y/N): 
if /I "!gen_enc!"=="Y" (
    for /f %%A in ('powershell -Command "[Convert]::ToBase64String((1..32 | %% { Get-Random -Minimum 0 -Maximum 256 }))"') do set enc_key=%%A
    call :update_config encryption_key "!enc_key!"
)

echo Installation complete.
echo Virtual environment created in venv
echo Configuration saved to config.toml

echo.
echo To launch the app, run:
echo    run.bat

goto :eof

:update_config
powershell -Command "(Get-Content config.toml) -replace '^\s*%1\s*=.*', '%1 = \"%2\"' | Set-Content config.toml"
goto :eof

:update_config_raw
powershell -Command "(Get-Content config.toml) -replace '^\s*%1\s*=.*', '%1 = %2' | Set-Content config.toml"
goto :eof
