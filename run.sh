#!/bin/bash
set -euo pipefail

# ====================================================================
#
#   Simplified LOLLMs - Installer & Runner for Linux/macOS (TTY-safe)
#
# ====================================================================

VENV_DIR="venv"
REQUIREMENTS_FILE="requirements.txt"
APP_MODULE="main:app"
PYTHON_EXECUTABLE="python3"

# Detect if stdout is a TTY
IS_TTY=0
if [ -t 1 ]; then
  IS_TTY=1
fi

# --- Style and Helper Functions (colors only if TTY) ---
if [ "$IS_TTY" -eq 1 ]; then
  COLOR_RESET=$'\e[0m'
  COLOR_INFO=$'\e[1;34m'
  COLOR_SUCCESS=$'\e[1;32m'
  COLOR_ERROR=$'\e[1;31m'
  COLOR_WARN=$'\e[1;33m'
  COLOR_HEADER=$'\e[1;35m'
else
  COLOR_RESET=''
  COLOR_INFO=''
  COLOR_SUCCESS=''
  COLOR_ERROR=''
  COLOR_WARN=''
  COLOR_HEADER=''
fi

print_header()  { echo -e "${COLOR_HEADER}===== $* =====${COLOR_RESET}"; }
print_info()    { echo -e "${COLOR_INFO}[INFO]${COLOR_RESET} $*"; }
print_success() { echo -e "${COLOR_SUCCESS}[SUCCESS]${COLOR_RESET} $*"; }
print_error()   { echo -e "${COLOR_ERROR}[ERROR]${COLOR_RESET} $*" >&2; }
print_warn()    { echo -e "${COLOR_WARN}[WARNING]${COLOR_RESET} $*"; }

# --- Initial System Checks ---

# Avoid clear in non-TTY contexts (systemd), and prefer tput when available
if [ "$IS_TTY" -eq 1 ]; then
  if command -v tput >/dev/null 2>&1; then
    tput reset || true
  fi
fi

print_header "Simplified LOLLMs Installer & Runner"
print_info "Performing initial system checks..."

# Pick python
if ! command -v python3 &>/dev/null; then
  if ! command -v python &>/dev/null; then
    print_error "Python not found. Please install Python 3.10 or newer."
    exit 1
  else
    PYTHON_EXECUTABLE="python"
  fi
fi

# Ensure venv module exists
if ! $PYTHON_EXECUTABLE -m venv -h &>/dev/null; then
  print_error "Python 'venv' module unavailable. Install it (e.g., 'sudo apt-get install python3-venv')."
  exit 1
fi

print_success "Python environment is ready."

# --- Setup or Start Logic ---
if [ ! -d "$VENV_DIR" ]; then
  print_header "[Step 1/2] Initial Setup"
  print_info "Virtual environment not found. Creating..."
  $PYTHON_EXECUTABLE -m venv "$VENV_DIR"
  print_success "Virtual environment created in '$VENV_DIR/'."

  print_header "[Step 2/2] Installing Dependencies"
  if [ -f "$REQUIREMENTS_FILE" ]; then
    # Use the venv's pip directly (no 'activate' needed, better for services)
    "$PWD/$VENV_DIR/bin/pip" install --no-cache-dir -r "$REQUIREMENTS_FILE"
    print_success "All dependencies installed."
  else
    print_error "'$REQUIREMENTS_FILE' not found. Cannot install dependencies."
    exit 1
  fi

  print_header "Setup Complete!"
else
  print_info "Virtual environment found."
fi

# --- .env File Check ---
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  print_info "'.env' file not found. Creating one from '.env.example'."
  cp ".env.example" ".env"
  print_success "'.env' file created. Edit it for custom configurations."
fi

# --- Resolve absolute paths for service-safe ExecStart ---
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHONPATH_VALUE="$PROJECT_DIR"
UVICORN_BIN="$PROJECT_DIR/$VENV_DIR/bin/uvicorn"

if [ ! -x "$UVICORN_BIN" ]; then
  print_error "uvicorn not found at '$UVICORN_BIN'. Did dependency install succeed?"
  exit 1
fi

# --- Determine port (prefer .env SERVER_PORT if present) ---
PORT_TO_USE="9642"
if [[ -f "$PROJECT_DIR/.env" ]]; then
  PORT_FROM_ENV="$(grep -E '^\s*SERVER_PORT\s*=' "$PROJECT_DIR/.env" | cut -d '=' -f2- | tr -d ' "'\'' | xargs || true)"'
  if [[ -n "${PORT_FROM_ENV:-}" ]]; then
    PORT_TO_USE="$PORT_FROM_ENV"
  fi
fi

# --- Optional systemd service creation (Linux only) ---
SERVICE_CREATED=false
if [[ "$(uname)" == "Linux" ]] && command -v systemctl &>/dev/null && [[ ! -f "/etc/systemd/system/simplified_lollms.service" ]]; then
  print_header "Optional: Create a systemd service"
  if [ "$IS_TTY" -eq 1 ]; then
    read -p "Create and enable a systemd service to run on boot? (y/n): " CREATE_SERVICE
  else
    # Non-interactive contexts should skip prompting
    CREATE_SERVICE="n"
    print_warn "Non-interactive context detected; skipping service creation prompt."
  fi

  if [[ "$CREATE_SERVICE" =~ ^[Yy]$ ]]; then
    SERVICE_FILE_PATH="/etc/systemd/system/simplified_lollms.service"
    print_info "Creating systemd service file at $SERVICE_FILE_PATH"

    # Use current user/group where possible
    RUN_USER="${SUDO_USER:-$USER}"
    RUN_GROUP="$(id -gn "$RUN_USER")"

    # Use EnvironmentFile for .env if present; otherwise set minimal env
    ENV_FILE_LINE=""
    if [[ -f "$PROJECT_DIR/.env" ]]; then
      ENV_FILE_LINE="EnvironmentFile=$PROJECT_DIR/.env"
    fi

    # Provide TERM=dumb to suppress TERM warnings in any subprocess that insists
    # and set PYTHONUNBUFFERED for better logging in journal
    read -r -d '' SERVICE_FILE_CONTENT <<EOF
[Unit]
Description=Simplified LOLLMs Service
After=network.target

[Service]
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${PROJECT_DIR}
Environment=PYTHONPATH=${PYTHONPATH_VALUE}
Environment=PYTHONUNBUFFERED=1
Environment=TERM=dumb
${ENV_FILE_LINE}
ExecStart=${UVICORN_BIN} ${APP_MODULE} --host 0.0.0.0 --port ${PORT_TO_USE}
Restart=on-failure
RestartSec=5
# Hardening (optional)
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

    print_warn "Root privileges are required to install the service."
    echo "$SERVICE_FILE_CONTENT" | sudo tee "$SERVICE_FILE_PATH" >/dev/null

    print_info "Reloading systemd daemon, enabling and starting the service..."
    sudo systemctl daemon-reload
    sudo systemctl enable "simplified_lollms.service"
    sudo systemctl start "simplified_lollms.service"

    print_header "Service Management"
    print_success "Service 'simplified_lollms' is now running."
    print_info "Check status: sudo systemctl status simplified_lollms"
    print_info "View logs:   sudo journalctl -u simplified_lollms -f"
    SERVICE_CREATED=true
  fi
fi

# --- Start Server in Foreground if Service Not Created ---
if [ "$SERVICE_CREATED" = false ]; then
  print_header "Starting Simplified LOLLMs (Foreground Mode)"
  export PYTHONPATH="$PYTHONPATH_VALUE"
  export PYTHONUNBUFFERED=1
  # Do not export TERM here; rely on real TTY if present

  print_info "Starting Uvicorn server on http://0.0.0.0:${PORT_TO_USE}"
  print_info "Press Ctrl+C to stop the server."
  echo

  # Use absolute uvicorn path; no 'activate' required and service-safe
  exec "$UVICORN_BIN" "$APP_MODULE" --host "0.0.0.0" --port "$PORT_TO_USE"
fi
