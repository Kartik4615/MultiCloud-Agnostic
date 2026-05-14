@echo off
echo ================================================
echo   MultiCloud Backend - Local Setup
echo ================================================
echo.

echo [1/3] Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: pip install failed. Make sure Python is installed.
    pause
    exit /b 1
)

echo.
echo [2/3] Dependencies installed successfully!
echo.
echo [3/3] Starting Flask server on http://localhost:5000
echo       Press Ctrl+C to stop.
echo.
python app.py
pause
