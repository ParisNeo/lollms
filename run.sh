#!/bin/bash

set -e  # Exit on any command failure

# Check for virtual environment existence
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found!"
    echo "Please run './install.sh' first to set up the application."
    exit 1
fi

# Check for main.py existence
if [ ! -f "main.py" ]; then
    echo "❌ Error: Main script 'main.py' not found in current directory!"
    exit 1
fi

# Activate virtual environment and run application
echo $'\n🔌 Activating virtual environment...'
source venv/bin/activate

echo "🚀 Starting Lollms Application..."
python main.py "$@"
