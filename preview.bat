@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ========================================
echo    Forest Island Daily - Local Preview
echo ========================================
echo.
echo Server: http://localhost:8000
echo Stop:   press Ctrl + C
echo.

start "" "http://localhost:8000"

python -m http.server 8000 2>nul || py -m http.server 8000 2>nul || (
    echo [X] python not found. Install Python 3.
    pause
)
