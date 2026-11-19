#!/bin/bash
set -euo pipefail

# ================================================================
#   LOLLMs - Runner & Updater (standalone uv)
# ================================================================
# Decision tree:
#   1) A working venv/ exists         -> activate + run. Done.
#   2) No working venv, uv found      -> use it to build venv/ + install deps.
#   3) No working venv, no uv         -> fetch a standalone uv, then (2).
#   4) No uv obtainable, system python -> legacy venv + pip fallback.
#
# Python version is pinned in PY_VERSION below (easy to bump).
# `uv` is NEVER reinstalled if already available (PATH or bundled ./uv).
# The venv/ folder layout is unchanged from previous releases.
# ================================================================

# ----- PYTHON VERSION (bump for future releases) -----------------
# Bump this single value on every release where you want a newer
# interpreter. `uv python install` will fetch exactly this version.
# Must be a real, released CPython version (e.g. 3.11, 3.12, 3.13).
PY_VERSION="3.11"
# -----------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="venv"
REQUIREMENTS_FILE="requirements.txt"
MAIN_SCRIPT="main.py"
UPDATE_FLAG_FILE="update_request.flag"
UV_EXE=""
UV_LOCAL="$SCRIPT_DIR/uv"

# ---- Colour helpers (TTY-aware) ----
IS_TTY=0
if [ -t 1 ]; then IS_TTY=1; fi
if [ "$IS_TTY" -eq 1 ]; then
  COLOR_RESET=$'\e[0m'; COLOR_INFO=$'\e[1;34m'; COLOR_SUCCESS=$'\e[1;32m'
  COLOR_ERROR=$'\e[1;31m'; COLOR_WARN=$'\e[1;33m'; COLOR_HEADER=$'\e[1;35m'
else
  COLOR_RESET=''; COLOR_INFO=''; COLOR_SUCCESS=''; COLOR_ERROR=''; COLOR_WARN=''; COLOR_HEADER=''
fi
print_header()  { echo -e "${COLOR_HEADER}===== $* =====${COLOR_RESET}"; }
print_info()    { echo -e "${COLOR_INFO}[INFO]${COLOR_RESET} $*"; }
print_success() { echo -e "${COLOR_SUCCESS}[SUCCESS]${COLOR_RESET} $*"; }
print_warn()    { echo -e "${COLOR_WARN}[WARNING]${COLOR_RESET} $*"; }
print_error()   { echo -e "${COLOR_ERROR}[ERROR]${COLOR_RESET} $*" >&2; }

trap "echo 'Stopping LOLLMs...'; exit 0" SIGTERM SIGINT

print_header "LOLLMs Runner"

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
uv_target_triple() {
    local os arch
    os="$(uname -s)"
    arch="$(uname -m)"
    case "$os" in
        Linux)
            case "$arch" in
                x86_64|amd64) echo "x86_64-unknown-linux-gnu" ;;
                aarch64|arm64) echo "aarch64-unknown-linux-gnu" ;;
                *) echo "" ;;
            esac ;;
        Darwin)
            case "$arch" in
                x86_64) echo "x86_64-apple-darwin" ;;
                arm64|aarch64) echo "aarch64-apple-darwin" ;;
                *) echo "" ;;
            esac ;;
        *) echo "" ;;
    esac
}

# Resolution order: PATH -> ./uv (bundled) -> download standalone -> pip install.
# Never reinstalls when already present.
ensure_uv() {
    # 1) Bundled next to this script wins over PATH so a shipped release is
    #    fully self-contained and reproducible (same policy as run.bat).
    if [ -x "$UV_LOCAL" ]; then
        UV_EXE="$UV_LOCAL"
        print_info "Using bundled uv: $UV_EXE"
        return 0
    fi
    # 2) PATH
    if command -v uv &>/dev/null; then
        UV_EXE="$(command -v uv)"
        print_info "uv already installed: $UV_EXE"
        return 0
    fi

    local triple
    triple="$(uv_target_triple)"
    if [ -n "$triple" ]; then
        print_info "uv not found. Downloading standalone uv ($triple)..."
        local url tmp
        url="https://github.com/astral-sh/uv/releases/latest/download/uv-${triple}.tar.gz"
        tmp="$(mktemp -d 2>/dev/null || mktemp -d -t uvdownload)"
        if ( command -v curl &>/dev/null && curl -fsSL "$url" -o "$tmp/uv.tar.gz" ) \
           || ( command -v wget &>/dev/null && wget -q "$url" -O "$tmp/uv.tar.gz" ); then
            if tar -xzf "$tmp/uv.tar.gz" -C "$tmp" 2>/dev/null; then
                local found
                found="$(find "$tmp" -type f -name uv -perm -u+x 2>/dev/null | head -n1)"
                if [ -n "$found" ]; then
                    cp "$found" "$UV_LOCAL"
                    chmod +x "$UV_LOCAL"
                    UV_EXE="$UV_LOCAL"
                    rm -rf "$tmp"
                    print_info "uv downloaded: $UV_EXE"
                    return 0
                fi
            fi
        fi
        rm -rf "$tmp"
    fi

    if command -v python3 &>/dev/null || command -v python &>/dev/null; then
        print_warn "Direct uv download failed. Trying pip install uv..."
        local PY
        PY="$(command -v python3 || command -v python)"
        if "$PY" -m pip install --user --upgrade uv >/dev/null 2>&1; then
            if command -v uv &>/dev/null; then
                UV_EXE="$(command -v uv)"
                print_info "uv installed via pip: $UV_EXE"
                return 0
            fi
            local candidate
            candidate="$("$PY" -c "import shutil;print(shutil.which('uv') or '')" 2>/dev/null || true)"
            if [ -n "$candidate" ] && [ -x "$candidate" ]; then
                UV_EXE="$candidate"
                print_info "uv installed via pip: $UV_EXE"
                return 0
            fi
        fi
    fi
    return 1
}

build_venv_with_uv() {
    print_info "Ensuring a managed Python $PY_VERSION toolchain..."
    if ! "$UV_EXE" python install "$PY_VERSION" >/dev/null 2>&1; then
        print_warn "Could not install managed Python $PY_VERSION; uv will use any available Python."
    fi

    print_info "Creating virtual environment in '$VENV_DIR'..."
    if ! "$UV_EXE" venv "$VENV_DIR" --python "$PY_VERSION" 2>/dev/null; then
        print_warn "$PY_VERSION venv failed; retrying with any available Python..."
        if ! "$UV_EXE" venv "$VENV_DIR"; then
            print_error "uv could not create the virtual environment."
            return 1
        fi
    fi

    print_info "Installing dependencies with uv..."
    "$UV_EXE" pip install --python "$VENV_DIR/bin/python" \
        --upgrade pip wheel setuptools || \
        print_warn "uv bootstrap of pip/wheel/setuptools failed; retrying via pip."

    if ! "$UV_EXE" pip install --python "$VENV_DIR/bin/python" \
            --no-cache-dir -r "$REQUIREMENTS_FILE"; then
        print_warn "uv dependency install failed. Retrying with pip inside venv..."
        # shellcheck disable=SC1091
        source "$VENV_DIR/bin/activate"
        pip install --upgrade pip wheel setuptools
        pip install --no-cache-dir -r "$REQUIREMENTS_FILE"
    fi
    print_success "Initial environment setup complete."
    return 0
}

legacy_pip_setup() {
    local PY
    if command -v python3 &>/dev/null; then PY="python3";
    elif command -v python &>/dev/null; then PY="python";
    else
        print_error "Neither uv nor Python is available. Cannot continue."
        return 1
    fi
    print_warn "Falling back to system $PY + pip..."
    if [ ! -x "$VENV_DIR/bin/python" ]; then
        "$PY" -m venv "$VENV_DIR" || return 1
    fi
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip wheel setuptools || return 1
    pip install --no-cache-dir -r "$REQUIREMENTS_FILE" || return 1
    print_success "Legacy pip setup complete."
    return 0
}

perform_update() {
    print_header "Updating LOLLMs"
    if [ -d ".git" ]; then
        print_info "Fetching latest updates..."
        git fetch --all --tags
        if git symbolic-ref -q HEAD > /dev/null 2>&1; then
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
        # shellcheck disable=SC1091
        source "$VENV_DIR/bin/activate"
        if [ -n "$UV_EXE" ]; then
            if ! "$UV_EXE" pip install --python "$VENV_DIR/bin/python" \
                    --no-cache-dir -r "$REQUIREMENTS_FILE"; then
                print_warn "uv update failed. Retrying with pip..."
                pip install --no-cache-dir -r "$REQUIREMENTS_FILE"
            fi
        else
            pip install --no-cache-dir -r "$REQUIREMENTS_FILE"
        fi
        print_success "Update successful."
    else
        print_error "Not a git repository. Skipping code update."
    fi
}

# ------------------------------------------------------------------
# STEP 1 - Fast path: working venv present -> just run.
# ------------------------------------------------------------------
if [ -x "$VENV_DIR/bin/python" ]; then
    print_info "Found existing virtual environment; skipping bootstrap."
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
else
    # --------------------------------------------------------------
    # STEP 2/3 - No venv. Need uv (found or fetched) to build it.
    # --------------------------------------------------------------
    if ! ensure_uv; then
        print_warn "uv unavailable. Attempting legacy system-Python fallback..."
        if ! legacy_pip_setup; then
            print_error "Bootstrap failed: install Python 3.10+ OR ensure internet access to fetch uv."
            exit 1
        fi
    else
        if ! build_venv_with_uv; then
            print_warn "uv venv setup failed. Attempting legacy system-Python fallback..."
            if ! legacy_pip_setup; then
                print_error "Bootstrap failed."
                exit 1
            fi
        fi
    fi
fi

# ------------------------------------------------------------------
# CLI argument parsing
# ------------------------------------------------------------------
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
        u_idx=$((i+1)); p_idx=$((i+2))
        if [ $u_idx -le $# ]; then RESET_USER="${!u_idx}"; fi
        if [ $p_idx -le $# ]; then RESET_PASS="${!p_idx}"; fi
    fi
done

if [ "$DO_UPDATE" -eq 1 ]; then
    perform_update
fi

if [ "$RESET_MODE" -eq 1 ]; then
    if [ -z "$RESET_USER" ] || [ -z "$RESET_PASS" ]; then
        print_error "Usage: ./run.sh --reset-password <username> <new_password>"
        exit 1
    fi
    print_info "Running Password Reset Tool..."
    export PYTHONPATH="$(pwd)"
    python reset_password.py "$RESET_USER" "$RESET_PASS"
    exit 0
fi

# ------------------------------------------------------------------
# First-run .env bootstrap
# ------------------------------------------------------------------
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    print_info "Configuring '.env' file for the first time..."
    cp ".env.example" ".env"
    print_info "Generating secure SECRET_KEY..."
    user_secret=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
    echo "SECRET_KEY=$user_secret" >> .env
    print_success "Security key configured."
fi

# ------------------------------------------------------------------
# Main execution loop
# ------------------------------------------------------------------
export PYTHONPATH="$(pwd)"
export PYTHONUNBUFFERED=1

print_info "Starting application loop. Updates will only run if triggered via UI."

while true; do
    if [ -f "$UPDATE_FLAG_FILE" ]; then
        print_info "Update flag detected (from UI). Starting update..."
        perform_update
        rm -f "$UPDATE_FLAG_FILE"
        print_info "Update finished. Restarting application..."
    fi

    print_info "Launching LOLLMs..."
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"

    python "$MAIN_SCRIPT" "$@" &
    PID=$!
    EXIT_CODE=0
    wait $PID || EXIT_CODE=$?
    print_info "Application exited with code $EXIT_CODE."
    sleep 2
done