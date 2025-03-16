@echo off
SETLOCAL EnableExtensions

REM Clock Overlay Application Launcher
echo Starting Clock Overlay Application...

REM Check if virtual environment exists
if not exist .venv\Scripts\activate.bat (
    echo Error: Virtual environment not found.
    echo Please ensure a virtual environment named "venv" exists in the same directory as this script.
    pause
    exit /b 1
)

REM Check if main.py exists
if not exist main.py (
    echo Error: main.py not found.
    echo Please ensure main.py is in the same directory as this script.
    pause
    exit /b 1
)

REM Activate virtual environment and run main.py
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to activate virtual environment.
    pause
    exit /b 1
)

echo Running Clock Overlay Application...
python main.py %*

REM Deactivate virtual environment
call venv\Scripts\deactivate.bat

echo Clock Overlay Application closed.
exit /b 0