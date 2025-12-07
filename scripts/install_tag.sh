#!/bin/bash
set -e

echo "=========================================="
echo "      LoLLMs Tag Installer (Linux/Mac)"
echo "=========================================="
echo ""

# 1. Verify Git Installation
if ! command -v git &> /dev/null; then
    echo "[ERROR] Git is not installed."
    echo "Please install git (e.g., sudo apt install git or brew install git) and try again."
    exit 1
fi

# 2. Get Tag Version
TAG=$1
if [ -z "$TAG" ]; then
    read -p "Enter the tag/version to install [default: v2.0.0]: " TAG
fi

if [ -z "$TAG" ]; then
    TAG="v2.0.0"
fi

# 3. Clone Repository
INSTALL_DIR="lollms_$TAG"
echo ""
echo "[INFO] Cloning LoLLMs (Tag: $TAG) into folder '$INSTALL_DIR'..."
echo ""

if git clone --branch "$TAG" --depth 1 https://github.com/ParisNeo/lollms.git "$INSTALL_DIR"; then
    # 4. Success & Instructions
    echo ""
    echo "=========================================="
    echo "[SUCCESS] Installation Complete!"
    echo "=========================================="
    echo ""
    echo "To start LoLLMs, run the following commands:"
    echo ""
    echo "   cd $INSTALL_DIR"
    echo "   ./run.sh"
    echo ""
else
    echo ""
    echo "[ERROR] Failed to clone repository."
    echo "Please check if the tag '$TAG' exists and if you have an internet connection."
    exit 1
fi
