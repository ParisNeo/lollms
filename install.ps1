Write-Host "Starting Lollms Installation Script"

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "Creating Python Virtual Environment..."
    python -m venv venv

    # Activate and install dependencies
    $activatePath = ".\venv\Scripts\Activate.ps1"
    if (Test-Path $activatePath) {
        # Temporarily change execution policy to run the activate script
        $currentPolicy = Get-ExecutionPolicy
        try {
            Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force
            & $activatePath
            
            if (Test-Path "requirements.txt") {
                Write-Host "Installing Python Dependencies..."
                pip install --upgrade pip | Out-Null
                pip install -r requirements.txt | Out-Null
            } else {
                Write-Warning "requirements.txt not found."
            }
        } finally {
            # Restore original execution policy
            Set-ExecutionPolicy -ExecutionPolicy $currentPolicy -Scope Process -Force
        }
    } else {
        Write-Warning "Virtual environment activation script not found."
    }
} else {
    Write-Host "Virtual environment already exists."
}

# Copy config_example.toml to config.toml if needed
if ((Test-Path "config_example.toml") -and -not (Test-Path "config.toml")) {
    Copy-Item "config_example.toml" "config.toml"
}

# Function to update config.toml
function Update-Config($key, $value, $isString) {
    $content = Get-Content "config.toml"
    if ($isString) {
        $content = $content -replace "^\s*$key\s*=.*", "$key = `"$value`""
    } else {
        $content = $content -replace "^\s*$key\s*=.*", "$key = $value"
    }
    Set-Content "config.toml" -Value $content
}

# Prompt for configuration values
$host = Read-Host -Prompt "Enter host [0.0.0.0]"
if ([string]::IsNullOrWhiteSpace($host)) { $host = "0.0.0.0" }
Update-Config "host" $host $true

$port = Read-Host -Prompt "Enter port [9642]"
if ([string]::IsNullOrWhiteSpace($port)) { $port = 9642 }
Update-Config "port" $port $false

# --- NEW: Firewall Rule Creation with Confirmation ---
Write-Host ""
Write-Host "Checking for Administrator privileges to manage firewall..."
try {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
    if ($principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host "Administrator privileges detected."
        $createRule = Read-Host -Prompt "Do you want to create a firewall rule to allow network access? (Y/n)"
        if ($createRule.ToLower() -ne 'n') {
            Write-Host "Attempting to create firewall rule..."
            $ruleName = "LoLLMs Web UI"
            $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
            if ($existingRule) {
                Write-Host "Firewall rule '$ruleName' already exists. Removing it to ensure the port is correct."
                Remove-NetFirewallRule -DisplayName $ruleName | Out-Null
            }
            New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $port | Out-Null
            Write-Host "Successfully created firewall rule for port $port to allow network access."
        } else {
            Write-Host "Skipping firewall rule creation. The app may not be accessible from other devices."
        }
    } else {
        throw "Not running as Administrator."
    }
} catch {
    Write-Warning "Administrator privileges not detected or an error occurred."
    Write-Warning "Please re-run this script as an Administrator if you want the option to create a firewall rule."
}
Write-Host ""
# --- END: Firewall Rule Creation ---

$data_dir = Read-Host -Prompt "Enter data_dir [data]"
if ([string]::IsNullOrWhiteSpace($data_dir)) { $data_dir = "data" }
Update-Config "data_dir" $data_dir $true

$db_url = Read-Host -Prompt "Enter database_url [sqlite:///./data/app_main.db]"
if ([string]::IsNullOrWhiteSpace($db_url)) { $db_url = "sqlite:///./data/app_main.db" }
Update-Config "database_url" $db_url $true

$gen_secret = Read-Host -Prompt "Generate new secret_key? (y/N)"
if ($gen_secret -eq 'y') {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $new_secret = [Convert]::ToBase64String($bytes)
    Update-Config "secret_key" $new_secret $true
}

# Safe store defaults
$chunk_size = Read-Host -Prompt "Enter chunk_size [4096]"
if ([string]::IsNullOrWhiteSpace($chunk_size)) { $chunk_size = 4096 }
Update-Config "chunk_size" $chunk_size $false

$chunk_overlap = Read-Host -Prompt "Enter chunk_overlap [200]"
if ([string]::IsNullOrWhiteSpace($chunk_overlap)) { $chunk_overlap = 200 }
Update-Config "chunk_overlap" $chunk_overlap $false

# Encryption key
$gen_enc = Read-Host -Prompt "Generate new encryption_key? (y/N)"
if ($gen_enc -eq 'y') {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $enc_key = [Convert]::ToBase64String($bytes)
    Update-Config "encryption_key" $enc_key $true
}


Write-Host ""
Write-Host "Installation complete."
Write-Host "Virtual environment created in venv"
Write-Host "Configuration saved to config.toml"
Write-Host ""
Write-Host "To launch the app, run:"
Write-Host "   .\run.ps1"