#!/bin/bash
set -euo pipefail

# ================================================================
#   LOLLMs – Installer & Runner (Restored & Enhanced)
# ================================================================

VENV_DIR="venv"
REQUIREMENTS_FILE="requirements.txt"
MAIN_SCRIPT="main.py"
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

print_header "LOLLMs Runner"

# --- 1. Argument Parsing ---
DO_UPDATE=0
RESET_MODE=0
RESET_USER=""
RESET_PASS=""

# Use a standard loop to detect flags
# We don't shift here because we want to pass "$@" to main.py later
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

# --- 2. Python Environment Check ---
if ! command -v python3 &>/dev/null; then
  if ! command -v python &>/dev/null; then
    print_error "Python not found. Please install Python 3.10+."
    exit 1
  else
    PYTHON_EXECUTABLE="python"
  fi
fi

# --- 3. Setup / Venv ---
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

# --- 4. Update Logic ---
if [ "$DO_UPDATE" -eq 1 ]; then
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
fi

# --- 5. Password Reset Mode ---
if [ "$RESET_MODE" -eq 1 ]; then
    if [ -z "$RESET_USER" ] || [ -z "$RESET_PASS" ]; then
        print_error "Usage: ./run.sh --reset-password <username> <new_password>"
        exit 1
    fi
    print_info "Running Password Reset Tool..."
    export PYTHONPATH="$(pwd)"
    python3 reset_password.py "$RESET_USER" "$RESET_PASS"
    exit 0
fi

# --- 6. Final Execution ---
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp ".env.example" ".env"
fi

export PYTHONPATH="$(pwd)"
export PYTHONUNBUFFERED=1

print_info "Launching LOLLMs with arguments: $*"
# Use exec to hand over the process to python, ensuring signals (Ctrl+C) are handled correctly
exec python3 "$MAIN_SCRIPT" "$@"
