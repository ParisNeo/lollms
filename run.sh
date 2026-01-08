#!/bin/bash
set -euo pipefail

# ================================================================
#   LOLLMs – Service-Compatible Runner & Updater
# ================================================================

VENV_DIR="venv"
REQUIREMENTS_FILE="requirements.txt"
MAIN_SCRIPT="main.py"
UPDATE_FLAG_FILE="update_request.flag"
PYTHON_EXECUTABLE="python3"

# Detect if stdout is a TTY for color output
IS_TTY=0
if [ -t 1 ]; then IS_TTY=1; fi

if [ "$IS_TTY" -eq 1 ]; then
  COLOR_RESET=$'\e[0m'
  COLOR_INFO=$'\e[1;34m'
  COLOR_SUCCESS=$'\e[1;32m'
  COLOR_ERROR=$'\e[1;31m'
  COLOR_HEADER=$'\e[1;35m'
else
  COLOR_RESET=''
  COLOR_INFO=''
  COLOR_SUCCESS=''
  COLOR_ERROR=''
  COLOR_HEADER=''
fi

print_header()  { echo -e "${COLOR_HEADER}===== $* =====${COLOR_RESET}"; }
print_info()    { echo -e "${COLOR_INFO}[INFO]${COLOR_RESET} $*"; }
print_success() { echo -e "${COLOR_SUCCESS}[SUCCESS]${COLOR_RESET} $*"; }
print_error()   { echo -e "${COLOR_ERROR}[ERROR]${COLOR_RESET} $*" >&2; }

# Trap interrupts to exit the loop cleanly
trap "echo 'Stopping LOLLMs...'; exit 0" SIGTERM SIGINT

print_header "LOLLMs Runner"

# --- 1. Python Environment Check ---
if ! command -v python3 &>/dev/null; then
  if ! command -v python &>/dev/null; then
    print_error "Python not found. Please install Python 3.10+."
    exit 1
  else
    PYTHON_EXECUTABLE="python"
  fi
else
    PYTHON_EXECUTABLE="python3"
fi

# --- 2. Setup / Venv ---
if [ ! -d "$VENV_DIR" ]; then
    print_info "Creating virtual environment..."
    $PYTHON_EXECUTABLE -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    print_info "Installing dependencies..."
    pip install --upgrade pip
    pip install --no-cache-dir -r "$REQUIREMENTS_FILE"
    print_success "Initial environment setup complete."
else
    source "$VENV_DIR/bin/activate"
fi

# --- 3. Initial Update Logic (CLI argument ONLY) ---
DO_UPDATE=0
RESET_MODE=0
RESET_USER=""
RESET_PASS=""

for ((i=1; i<=$#; i++)); do
    arg="${!i}"
    if [ "$arg" == "--update" ]; then
        DO_UPDATE=1
    elif [ "$arg" == "--reset-password" ]; then
        RESET_MODE=1
        u_idx=$((i+1))
        p_idx=$((i+2))
        if [ $u_idx -le $# ]; then RESET_USER="${!u_idx}"; fi
        if [ $p_idx -le $# ]; then RESET_PASS="${!p_idx}"; fi
    fi
done

perform_update() {
    print_header "Updating LOLLMs"
    if [ -d ".git" ]; then
        print_info "Fetching latest updates..."
        git fetch --all --tags
        
        if git symbol-ref -q HEAD > /dev/null 2>&1; then
            print_info "Updating branch..."
            git pull
        else
            LATEST_TAG=$(git describe --tags "$(git rev-list --tags --max-count=1)" 2>/dev/null || true)
            if [ -n "$LATEST_TAG" ]; then
                print_info "Checking out latest tag: $LATEST_TAG"
                git checkout "$LATEST_TAG"
            else
                git pull
            fi
        fi
        print_info "Updating dependencies..."
        pip install --no-cache-dir -r "$REQUIREMENTS_FILE"
        print_success "Update successful."
    else
        print_error "Not a git repository. Skipping code update."
    fi
}

# Only update if explicitly requested via CLI argument
if [ "$DO_UPDATE" -eq 1 ]; then
    perform_update
fi

# --- 4. Password Reset Mode ---
if [ "$RESET_MODE" -eq 1 ]; then
    if [ -z "$RESET_USER" ] || [ -z "$RESET_PASS" ]; then
        print_error "Usage: ./run.sh --reset-password <username> <new_password>"
        exit 1
    fi
    print_info "Running Password Reset Tool..."
    export PYTHONPATH="$(pwd)"
    $PYTHON_EXECUTABLE reset_password.py "$RESET_USER" "$RESET_PASS"
    exit 0
fi

# --- 5. Environment Setup ---
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        print_info "Configuring '.env' file for the first time..."
        cp ".env.example" ".env"
        
        # Only prompt for key if running interactively
        if [ -t 0 ]; then
             echo "A SECRET_KEY is required."
             read -p "Enter a random secret string (or press Enter to auto-generate): " user_secret || true
        else
             user_secret=""
        fi
        
        if [ -z "$user_secret" ]; then
            if command -v openssl >/dev/null 2>&1; then
                user_secret=$(openssl rand -hex 32)
            else
                user_secret=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)
            fi
        fi
        
        echo "SECRET_KEY=$user_secret" >> .env
        print_success "Security key configured."
    fi
fi

# --- 6. Main Execution Loop ---
export PYTHONPATH="$(pwd)"
export PYTHONUNBUFFERED=1

print_info "Starting application loop. Updates will only run if triggered via UI."

while true; do
    # Check for update request flag from UI (Manual Trigger)
    if [ -f "$UPDATE_FLAG_FILE" ]; then
        print_info "Update flag detected (from UI). Starting update..."
        perform_update
        rm -f "$UPDATE_FLAG_FILE"
        print_info "Update finished. Restarting application..."
    fi

    print_info "Launching LOLLMs..."
    
    # Use the detected python executable
    $PYTHON_EXECUTABLE "$MAIN_SCRIPT" "$@" &
    PID=$!
    
    wait $PID
    EXIT_CODE=$?
    
    print_info "Application exited with code $EXIT_CODE."
    
    # Simple delay to prevent rapid looping on crash
    sleep 2
done
