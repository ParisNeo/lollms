@echo off
setlocal

:: Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found. Please run install.bat first.
    exit /b 1
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Run the app
python main.py

:: Deactivate is automatic on script end
