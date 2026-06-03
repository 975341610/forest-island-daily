@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ========================================
echo    Forest Island Daily - Auto Push
echo ========================================
echo.

if not exist "data\today.json" (
    echo [X] data\today.json not found
    echo.
    echo Please:
    echo   1. Open Feishu DM, find today.json sent by Mira
    echo   2. Right-click - Save As - save to %CD%\data\today.json
    echo   3. Re-run this script
    echo.
    pause
    exit /b 1
)

python -c "import json; json.load(open('data/today.json',encoding='utf-8'))" >nul 2>&1
if errorlevel 1 (
    echo [X] today.json is not valid JSON
    pause
    exit /b 1
)

for /f "delims=" %%i in ('python -c "import json; print(len(json.load(open(\"data/today.json\",encoding=\"utf-8\"))))"') do set COUNT=%%i
echo [v] today.json detected ^(%COUNT% items^)
echo.

if not exist ".git" (
    echo [X] Not a git repository
    pause
    exit /b 1
)

echo [^>] Merging into archive...
python scripts\generate.py
echo.

git add data\
git diff --cached --quiet
if not errorlevel 1 (
    echo [!] No new content
    pause
    exit /b 0
)

for /f "tokens=2 delims==" %%a in ('"wmic os get LocalDateTime /value | findstr ="') do set DT=%%a
set TODAY=%DT:~0,4%-%DT:~4,2%-%DT:~6,2%

echo [^>] Commit and push...
git commit -m "mira daily: %TODAY%"
git push

if errorlevel 1 (
    echo.
    echo [X] Push failed. Check network/permission.
) else (
    echo.
    echo [v] Push succeeded! Site will update in 1-2 minutes.
)

echo.
pause
