#!/bin/bash
set -euo pipefail

# ==========================================================
#   Simplified LOLLMs – Installer & Runner (TTY‑safe)
# ==========================================================

VENV_DIR="venv"
REQUIREMENTS_FILE="requirements.txt"
APP_MODULE="main:app"
PYTHON_EXECUTABLE="python3"

# Detect if stdout is a TTY
IS_TTY=0
if [ -t 1 ]; then
  IS_TTY=1
fi

# --- Colours (only if TTY) ---
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

# --- Initial system checks ---
if [ "$IS_TTY" -eq 1 ] && command -v tput >/dev/null 2>&1; then
  tput reset || true
fi

print_header "Simplified LOLLMs Installer & Runner"
print_info "Performing initial system checks..."

# Choose Python interpreter
if ! command -v python3 &>/dev/null; then
  if ! command -v python &>/dev/null; then
    print_error "Python not found. Please install Python 3.10 or newer."
    exit 1
  else
    PYTHON_EXECUTABLE="python"
  fi
fi

# Verify venv module
if ! $PYTHON_EXECUTABLE -m venv -h &>/dev/null; then
  print_error "Python 'venv' module unavailable. Install it (e.g., 'sudo apt-get install python3-venv')."
  exit 1
fi

print_success "Python environment is ready."

# --- Setup (only when a TTY is present) ---
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

# --- .env handling (only when a TTY is present) ---
if [ "$IS_TTY" -eq 1 ] && [ ! -f ".env" ] && [ -f ".env.example" ]; then
  print_info "'.env' file not found. Creating one from '.env.example'."
  cp ".env.example" ".env"
  print_success "'.env' file created. Edit it for custom configurations."
fi

# --- Parse optional host/port arguments ---
HOST_VAL=""
PORT_VAL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      if [[ -n "${2-}" && ! "$2" =~ ^-- ]]; then
        HOST_VAL="$2"
        shift 2
      else
        print_error "Missing value for --host"
        exit 1
      fi
      ;;
    --port)
      if [[ -n "${2-}" && ! "$2" =~ ^-- ]]; then
        PORT_VAL="$2"
        shift 2
      else
        print_error "Missing value for --port"
        exit 1
      fi
      ;;
    *)
      print_error "Unknown option: $1"
      exit 1
      ;;
  esac
done

# --- Paths ---
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHONPATH_VALUE="$PROJECT_DIR"
UVICORN_BIN="$PROJECT_DIR/$VENV_DIR/bin/uvicorn"

if [ ! -x "$UVICORN_BIN" ]; then
  print_error "uvicorn not found at '$UVICORN_BIN'. Did dependency install succeed?"
  exit 1
fi

# --- Start server (foreground, service‑safe) ---
print_header "Starting Simplified LOLLMs"
export PYTHONPATH="$PYTHONPATH_VALUE"
export PYTHONUNBUFFERED=1

print_info "Launching Uvicorn server"
if [ "$IS_TTY" -eq 1 ]; then
  print_info "Press Ctrl+C to stop the server."
fi
echo

# Build command array – only add host/port if supplied
CMD=("$UVICORN_BIN" "$APP_MODULE")
if [[ -n "$HOST_VAL" ]]; then
  CMD+=(--host "$HOST_VAL")
fi
if [[ -n "$PORT_VAL" ]]; then
  CMD+=(--port "$PORT_VAL")
fi
echo "${CMD[@]}"
exec "${CMD[@]}"
