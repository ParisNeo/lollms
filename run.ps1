# Run.ps1

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

Write-Color "🚀 Starting Lollms App" "Cyan"

# Check if virtual environment exists
if (-not (Test-Path -Path "venv\Scripts\Activate.ps1")) {
    Write-Color "❌ Virtual environment not found. Please run install.ps1 first." "Red"
    exit 1
}

# Activate virtual environment
Write-Color "🔧 Activating Virtual Environment..." "Green"
. .\venv\Scripts\Activate.ps1

# Run the Python app (main.py)
Write-Color "🔧 Running the app..." "Green"
python main.py

# Deactivate automatically when done
Write-Color "✅ App execution finished!" "Green"
