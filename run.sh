#!/bin/bash
set -euo pipefail

# ====================================================================
#
#   Simplified LOLLMs - Installer & Runner for Linux/macOS
#
# ====================================================================

VENV_DIR="venv"
REQUIREMENTS_FILE="requirements.txt"
APP_MODULE="main:app"
PYTHON_EXECUTABLE="python3"

# --- Style and Helper Functions ---
COLOR_RESET='\e[0m'
COLOR_INFO='\e[1;34m'
COLOR_SUCCESS='\e[1;32m'
COLOR_ERROR='\e[1;31m'
COLOR_WARN='\e[1;33m'
COLOR_HEADER='\e[1;35m'

print_header()  { echo -e "\n${COLOR_HEADER}=====================================================${COLOR_RESET}"; \
                  echo -e "${COLOR_HEADER}$1${COLOR_RESET}"; \
                  echo -e "${COLOR_HEADER}=====================================================${COLOR_RESET}"; }
print_info()    { echo -e "${COLOR_INFO}[INFO]${COLOR_RESET} $*"; }
print_success() { echo -e "${COLOR_SUCCESS}[SUCCESS]${COLOR_RESET} $*"; }
print_error()   { echo -e "${COLOR_ERROR}[ERROR]${COLOR_RESET} $*" >&2; }
print_warn()    { echo -e "${COLOR_WARN}[WARNING]${COLOR_RESET} $*"; }

# --- Initial System Checks ---
clear
print_header "    Simplified LOLLMs Installer & Runner"
print_info "Performing initial system checks..."

if ! command -v python3 &>/dev/null; then
    if ! command -v python &>/dev/null; then
        print_error "Python not found. Please install Python 3.10 or newer."
        exit 1
    else
        PYTHON_EXECUTABLE="python"
    fi
fi

if ! $PYTHON_EXECUTABLE -m venv -h &>/dev/null; then
    print_error "The 'venv' module for Python is not available. Please install it (e.g., 'sudo apt-get install python3-venv')."
    exit 1
fi
print_success "Python environment is ready."

# --- Setup or Start Logic ---
if [ ! -d "$VENV_DIR" ]; then
    print_header "--- [Step 1/2] Initial Setup ---"
    print_info "Virtual environment not found. Creating..."
    $PYTHON_EXECUTABLE -m venv "$VENV_DIR"
    print_success "Virtual environment created in '$VENV_DIR/'."

    print_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"

    print_header "--- [Step 2/2] Installing Dependencies ---"
    if [ -f "$REQUIREMENTS_FILE" ]; then
        pip install --no-cache-dir -r "$REQUIREMENTS_FILE"
        print_success "All dependencies installed."
    else
        print_error "'$REQUIREMENTS_FILE' not found. Cannot install dependencies."
        exit 1
    fi
    print_header "--- Setup Complete! ---"
else
    print_info "Virtual environment found. Activating..."
    source "$VENV_DIR/bin/activate"
fi

# --- .env File Check ---
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    print_info "'.env' file not found. Creating one from '.env.example'."
    cp ".env.example" ".env"
    print_success "'.env' file created. You may want to edit it for custom configurations."
fi

# --- Optional Systemd Service Creation (Linux Only) ---
SERVICE_CREATED=false
if [[ "$(uname)" == "Linux" ]] && command -v systemctl &>/dev/null && [[ ! -f "/etc/systemd/system/simplified_lollms.service" ]]; then
    print_header "--- Optional: Create a Systemd Service ---"
    read -p "Create and enable a systemd service to run on boot? (y/n): " CREATE_SERVICE
    if [[ "$CREATE_SERVICE" =~ ^[Yy]$ ]]; then
        SERVICE_FILE_PATH="/etc/systemd/system/simplified_lollms.service"
        print_info "Creating systemd service file at $SERVICE_FILE_PATH"
        PROJECT_DIR=$(pwd)
        
        PORT_TO_USE="9642"
        if [[ -f ".env" ]]; then
            PORT_FROM_ENV=$(grep -E '^\s*SERVER_PORT\s*=' .env | cut -d '=' -f2 | tr -d ' "'\' | xargs)
            if [[ -n "$PORT_FROM_ENV" ]]; then
                PORT_TO_USE="$PORT_FROM_ENV"
            fi
        fi

        SERVICE_FILE_CONTENT=$(cat << EOF
[Unit]
Description=Simplified LOLLMs Service
After=network.target

[Service]
User=${USER}
Group=$(id -gn ${USER})
WorkingDirectory=${PROJECT_DIR}
Environment="PYTHONPATH=${PROJECT_DIR}"
ExecStart=${PROJECT_DIR}/${VENV_DIR}/bin/uvicorn ${APP_MODULE} --host 0.0.0.0 --port ${PORT_TO_USE}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
)
        print_warn "Root privileges are required to install the service."
        echo "$SERVICE_FILE_CONTENT" | sudo tee "$SERVICE_FILE_PATH" > /dev/null
        
        print_info "Reloading systemd daemon, enabling and starting the service..."
        sudo systemctl daemon-reload
        sudo systemctl enable "simplified_lollms.service"
        sudo systemctl start "simplified_lollms.service"
        
        print_header "--- Service Management ---"
        print_success "Service 'simplified_lollms' is now running."
        print_info "Check status with: sudo systemctl status simplified_lollms"
        print_info "View logs with: sudo journalctl -u simplified_lollms -f"
        SERVICE_CREATED=true
    fi
fi


# --- Start Server in Foreground if Service Not Created ---
if [ "$SERVICE_CREATED" = false ]; then
    print_header "--- Starting Simplified LOLLMs (Foreground Mode) ---"
    export PYTHONPATH=.
    
    PORT_TO_USE="9642"
    if [[ -f ".env" ]]; then
        PORT_FROM_ENV=$(grep -E '^\s*SERVER_PORT\s*=' .env | cut -d '=' -f2 | tr -d ' "'\' | xargs)
        if [[ -n "$PORT_FROM_ENV" ]]; then
            PORT_TO_USE="$PORT_FROM_ENV"
        fi
    fi

    print_info "Starting Uvicorn server on http://0.0.0.0:${PORT_TO_USE}"
    print_info "Press Ctrl+C to stop the server."
    echo
    exec uvicorn "$APP_MODULE" --host "0.0.0.0" --port "$PORT_TO_USE"
fi