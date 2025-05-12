#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting Lollms Installation Script"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "🔧 Creating Python Virtual Environment..."
    python3 -m venv venv

    # Activate the virtual environment
    source ./venv/bin/activate

    # Install requirements if file exists
    if [ -f "requirements.txt" ]; then
        echo "📦 Installing Python Dependencies..."
        pip install --upgrade pip > /dev/null 2>&1
        pip install -r requirements.txt > /dev/null 2>&1
    else
        echo "⚠️ Warning: Requirements file not found. Please run 'pip freeze > requirements.txt' to create one."
    fi

else
    echo "✅ Virtual environment already exists"
fi

# Copy config if example exists and target doesn't exist
if [ -f "config_example.toml" ] && [ ! -f "config.toml" ]; then
    cp config_example.toml config.toml
fi

# Function to update TOML values with user input
update_config() {
    local key="$1"
    local default_value="$2"
    read -p "Enter value for $key [$default_value]: " new_val

    # Use user input if provided, otherwise keep default
    if [ -z "$new_val" ]; then
        new_val="$default_value"
    fi
    sed -i "/$key =/c\\$key = \"$new_val\"" config.toml
}

# Function to update TOML values with user input (for non-string values)
update_config_raw() {
    local key="$1"
    local default_value="$2"
    read -p "Enter value for $key [$default_value]: " new_val

    # Use user input if provided, otherwise keep default
    if [ -z "$new_val" ]; then
        new_val="$default_value"
    fi
    sed -i "/$key =/c\\$key = $new_val" config.toml
}

# Function to update TOML values with secure input (no echo)
update_config_secure() {
    local key="$1"
    read -s -p "Enter value for $key [****]: " new_val
    echo

    # Use user input if provided, otherwise keep default
    if [ -z "$new_val" ]; then
        new_val="CHANGE_ME_TO_A_STRONG_PASSWORD"
    fi
    sed -i "/$key =/c\\$key = \"$new_val\"" config.toml
}

# Server settings
echo $'\n🔧 Configure [server] Settings'
update_config "host" "\"0.0.0.0\""
update_config_raw "port" 9642

# App settings
echo $'\n🔧 Configure [app_settings] Settings'
update_config "data_dir" "\"data\""
update_config "database_url" "\"sqlite:///./data/app_main.db\""

# Secret key generation
read -p $'Generate new secret_key? (y/N) [N]: ' gen_secret
if [[ "$gen_secret" == "Y" || "$gen_secret" == "y" ]]; then
    new_secret=$(openssl rand -base64 32)
    sed -i "/secret_key =/c\\secret_key = \"$new_secret\"" config.toml
fi

# Initial admin user
echo $'\n🔧 Configure [initial_admin_user] Settings'
update_config "username" "\"superadmin\""
read -p $'Generate secure password? (y/N) [N]: ' gen_pass
if [[ "$gen_pass" == "Y" || "$gen_pass" == "y" ]]; then
    new_password=$(openssl rand -base64 20)
    echo $'\n🔐 Generated password: '$new_password$' (will be hashed in DB)'
else
    update_config_secure "password"
fi

# Lollms client defaults
echo $'\n🔧 Configure [lollms_client_defaults] Settings'
update_config "binding_name" "\"ollama\""
update_config "default_model_name" "\"phi4:latest\""
update_config "host_address" "\"http://localhost:11434\""
update_config "service_key_env_var" "\"OPENAI_API_KEY\""

# Safe store defaults
echo $'\n🔧 Configure [safe_store_defaults] Settings'
update_config_raw "chunk_size" 512
update_config_raw "chunk_overlap" 50

# Encryption key generation
read -p $'Generate new encryption_key? (y/N) [N]: ' gen_encryption
if [[ "$gen_encryption" == "Y" || "$gen_encryption" == "y" ]]; then
    new_enc_key=$(openssl rand -base64 32)
    sed -i "/encryption_key =/c\\encryption_key = \"$new_enc_key\"" config.toml
fi

# Final message
echo $'\n✅ Installation complete!'
echo "Virtual environment created in venv"
echo "Configuration saved to config.toml"

if [ -f "venv/bin/activate" ]; then
    echo $'\nTo activate the virtual environment:'
    echo 'source ./venv/bin/activate'
fi

echo "You can now start your application!"

# Create a new user and group named lollms
echo "🔧 Creating user and group 'lollms'..."
sudo groupadd lollms
sudo useradd -r -s /bin/false -g lollms lollms

# Create data directory if it doesn't exist and set permissions
echo "🔧 Creating data directory and setting permissions..."
if [ ! -d "data" ]; then
    mkdir data
fi
sudo chown -R lollms:lollms data

# Option to create a systemd service
read -p $'Create a systemd service to run the server? (y/N) [N]: ' create_service
if [[ "$create_service" == "Y" || "$create_service" == "y" ]]; then
    echo "🔧 Creating systemd service..."

    # Define the service file content
    cat <<EOF > lollms.service
[Unit]
Description=Lollms Application
After=network.target

[Service]
User=lollms
Group=lollms
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/run.sh
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    # Move the service file to the systemd directory
    sudo mv lollms.service /etc/systemd/system/

    # Reload systemd to recognize the new service
    sudo systemctl daemon-reload

    # Enable the service to start on boot
    sudo systemctl enable lollms.service

    echo "🔧 Systemd service created and enabled. You can now manage the service with the following commands:"
    echo "  - Start: sudo systemctl start lollms.service"
    echo "  - Stop: sudo systemctl stop lollms.service"
    echo "  - Restart: sudo systemctl restart lollms.service"
    echo "  - Status: sudo systemctl status lollms.service"
    echo "  - Enable (start on boot): sudo systemctl enable lollms.service"
    echo "  - Disable (do not start on boot): sudo systemctl disable lollms.service"
else
    echo "Systemd service creation skipped."
fi

echo "🚀 Installation complete!"
