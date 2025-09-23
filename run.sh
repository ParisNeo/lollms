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
if [ "$IS_TTY" -eq 1 ] && command -v tput >/dev/null 2>&1; then
  tput reset || true
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

# --- Setup (only in TTY) ---
if [ ! -d "$VENV_DIR" ]; then
  if [ "$IS_TTY" -eq 1 ]; then
    print_header "[Step 1/2] Initial Setup"
    print_info "Virtual environment not found. Creating..."
    $PYTHON_EXECUTABLE -m venv "$VENV_DIR"
    print_success "Virtual environment created in '$VENV_DIR/'."

    print_header "[Step 2/2] Installing Dependencies"
    if [ -f "$REQUIREMENTS_FILE" ]; then
      "$PWD/$VENV_DIR/bin/pip" install --no-cache-dir -r "$REQUIREMENTS_FILE"
      print_success "All dependencies installed."
    else
      print_error "'$REQUIREMENTS_FILE' not found. Cannot install dependencies."
      exit 1
    fi

    print_header "Setup Complete!"
  else
    print_error "Virtual environment not found and no TTY available. Aborting."
    exit 1
  fi
else
  print_info "Virtual environment found."
fi

# --- .env File Check (only in TTY) ---
if [ "$IS_TTY" -eq 1 ] && [ ! -f ".env" ] && [ -f ".env.example" ]; then
  print_info "'.env' file not found. Creating one from '.env.example'."
  cp ".env.example" ".env"
  print_success "'.env' file created. Edit it for custom configurations."
fi

# --- Paths ---
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
  PORT_FROM_ENV="$(grep -E '^\s*SERVER_PORT\s*=' "$PROJECT_DIR/.env" \
    | cut -d '=' -f2- \
    | tr -d " '\"" \
    | xargs || true)"
  if [[ -n "${PORT_FROM_ENV:-}" ]]; then
    PORT_TO_USE="$PORT_FROM_ENV"
  fi
fi

# --- Start Server (always foreground, service-safe) ---
print_header "Starting Simplified LOLLMs"
export PYTHONPATH="$PYTHONPATH_VALUE"
export PYTHONUNBUFFERED=1

print_info "Starting Uvicorn server on http://0.0.0.0:${PORT_TO_USE}"
if [ "$IS_TTY" -eq 1 ]; then
  print_info "Press Ctrl+C to stop the server."
fi
echo

exec "$UVICORN_BIN" "$APP_MODULE" --host "0.0.0.0" --port "$PORT_TO_USE"
