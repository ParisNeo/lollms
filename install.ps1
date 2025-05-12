# Install.ps1

# Function to print colored text
function Write-Color {
    param (
        [string]$text,
        [string]$color = "White"
    )
    $ColorEnum = [System.Enum]::GetValues([System.ConsoleColor]) | Where-Object { $_ -match $color }
    $Host.UI.RawUI.ForegroundColor = $ColorEnum[0]
    Write-Host $text
    $Host.UI.RawUI.ForegroundColor = "White"
}

Write-Color "🚀 Starting Lollms Installation Script" "Cyan"

# Check if venv exists
if (-not (Test-Path -Path "venv")) {
    Write-Color "🔧 Creating Python Virtual Environment..." "Green"
    python -m venv venv

    # Activate the virtual environment
    .\venv\Scripts\Activate.ps1

    # Install dependencies if requirements.txt exists
    if (Test-Path -Path "requirements.txt") {
        Write-Color "📦 Installing Python Dependencies..." "Green"
        pip install --upgrade pip
        pip install -r requirements.txt
    } else {
        Write-Color "⚠️ Warning: requirements.txt not found. Please create it!" "Yellow"
    }
} else {
    Write-Color "✅ Virtual environment already exists" "Green"
}

# Copy config_example.toml to config.toml if not already there
if (Test-Path -Path "config_example.toml" -and -not (Test-Path -Path "config.toml")) {
    Write-Color "🔧 Copying config_example.toml to config.toml" "Green"
    Copy-Item "config_example.toml" "config.toml"
}

# Update configuration interactively
function Update-Config {
    param (
        [string]$key,
        [string]$defaultValue
    )
    $newVal = Read-Host "Enter value for $key [$defaultValue]"
    if ($newVal -eq "") { $newVal = $defaultValue }
    (Get-Content config.toml) -replace "^\s*$key\s*=.*", "$key = `"$newVal`"" | Set-Content config.toml
}

Write-Color "🔧 Configure [server] Settings" "Green"
Update-Config "host" "0.0.0.0"
Update-Config "port" "9642"

Write-Color "🔧 Configure [app_settings] Settings" "Green"
Update-Config "data_dir" "data"
Update-Config "database_url" "sqlite:///./data/app_main.db"

Write-Color "🔧 Configure [initial_admin_user] Settings" "Green"
Update-Config "username" "superadmin"
$password = Read-Host "Enter password [default is 'CHANGE_ME']"
if ($password -eq "") { $password = "CHANGE_ME" }
Update-Config "password" $password

Write-Color "✅ Installation Complete!" "Cyan"
Write-Color "Virtual environment created in venv" "Green"
Write-Color "Configuration saved to config.toml" "Green"
Write-Color "You can now start your application!" "Green"
