@echo off
setlocal
:: Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found. Please run install.bat first.
    exit /b 1
)

echo welcome to lollms
:: Activate virtual environment
call .\venv\Scripts\activate.bat

echo Running server
:: Run the app
python main.py

:: Deactivate is automatic on script end
