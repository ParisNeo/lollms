@echo off
set ERRORLEVEL=0

if not exist "venv" (
    echo ❌ Error: Virtual environment not found!
    echo Please run './install.sh' first to set up the application.
    exit 1
)

if not exist "main.py" (
    echo ❌ Error: Main script 'main.py' not found in current directory!
    exit 1
)

echo 🌠 Activating virtual environment...
call venv\Scripts\activate

echo 🚀 Starting Lollms Application...
python main.py %*
