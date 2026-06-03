@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set LOG=deploy.log
echo === Deploy started at %DATE% %TIME% === > "%LOG%"

cls
echo.
echo ========================================
echo    Forest Island Daily - Deploy Wizard
echo ========================================
echo.
echo This script will help you:
echo   1. Check environment (git / python)
echo   2. Initialize git repository
echo   3. Configure GitHub remote
echo   4. First commit and push
echo   5. Guide you to enable GitHub Pages
echo.
echo NOTE: full log is saved to deploy.log
echo       If window closes unexpectedly, open deploy.log to debug.
echo.
pause

REM ===========================================
REM Step 0
REM ===========================================
echo. & echo ----- Step 0 / 5: Pre-flight check -----
echo [Step 0] Pre-flight >> "%LOG%"
echo.
echo [IMPORTANT] Before continuing, make sure you have already
echo created an EMPTY repository on GitHub:
echo.
echo   - Open: https://github.com/new
echo   - Repository name: forest-island-daily
echo   - DO NOT tick README / .gitignore / license
echo   - Click "Create repository"
echo.

set REPO_READY=
set /p REPO_READY=Have you created the empty repo on GitHub? (y/N):
echo Step 0 answer: [%REPO_READY%] >> "%LOG%"

if /i not "%REPO_READY%"=="y" goto need_repo
echo [v] OK, continuing
goto step1

:need_repo
echo.
echo [X] Please create empty repo at https://github.com/new first
echo     then re-run this script.
goto fatal

REM ===========================================
REM Step 1
REM ===========================================
:step1
echo. & echo ----- Step 1 / 5: Environment check -----
echo [Step 1] Environment check >> "%LOG%"

where git >nul 2>nul
if errorlevel 1 goto no_git
echo [v] git installed

where python >nul 2>nul
if not errorlevel 1 goto py_ok
where py >nul 2>nul
if errorlevel 1 goto no_py
:py_ok
echo [v] python installed

set MISSING=0
if not exist "index.html"                    set MISSING=1
if not exist "data\archive.json"             set MISSING=1
if not exist "scripts\generate.py"           set MISSING=1
if not exist ".github\workflows\daily.yml"   set MISSING=1
if "%MISSING%"=="1" goto files_missing
echo [v] Project files OK
goto step2

:no_git
echo [X] git not found
echo     install: https://git-scm.com/download/win
goto fatal

:no_py
echo [X] python not found
echo     install Python 3: https://www.python.org/downloads/
goto fatal

:files_missing
echo [X] Project files incomplete, please re-extract the zip
goto fatal

REM ===========================================
REM Step 2 - git identity
REM ===========================================
:step2
echo. & echo ----- Step 2 / 5: Check git identity -----
echo [Step 2] Git identity >> "%LOG%"

set GIT_NAME=
set GIT_EMAIL=
for /f "delims=" %%a in ('git config --global user.name 2^>nul') do set GIT_NAME=%%a
for /f "delims=" %%a in ('git config --global user.email 2^>nul') do set GIT_EMAIL=%%a

if not "%GIT_NAME%"=="" goto have_name
set /p GIT_NAME=Enter your GitHub username:
if "!GIT_NAME!"=="" goto empty_name
git config --global user.name "!GIT_NAME!"

:have_name
if not "%GIT_EMAIL%"=="" goto have_email
set /p GIT_EMAIL=Enter your GitHub email:
if "!GIT_EMAIL!"=="" goto empty_email
git config --global user.email "!GIT_EMAIL!"

:have_email
echo [v] git user.name  = %GIT_NAME%
echo [v] git user.email = %GIT_EMAIL%
goto step3

:empty_name
echo [X] Username cannot be empty
goto fatal

:empty_email
echo [X] Email cannot be empty
goto fatal

REM ===========================================
REM Step 3 - git init
REM ===========================================
:step3
echo. & echo ----- Step 3 / 5: Initialize git -----
echo [Step 3] Git init >> "%LOG%"

if exist ".git" goto skip_init
git init
if errorlevel 1 goto init_fail
echo [v] git init done
goto check_gitignore

:skip_init
echo [!] .git already exists, skipping init

:check_gitignore
if exist ".gitignore" goto step4
(
    echo .DS_Store
    echo *.log
    echo __pycache__/
    echo *.pyc
    echo .vscode/
    echo .idea/
    echo node_modules/
) > .gitignore
echo [v] .gitignore created
goto step4

:init_fail
echo [X] git init failed
goto fatal

REM ===========================================
REM Step 4 - remote (FLAT, no nested if blocks)
REM ===========================================
:step4
echo. & echo ----- Step 4 / 5: Configure GitHub remote -----
echo [Step 4.1] checking existing remote >> "%LOG%"

set EXISTING_REMOTE=
for /f "delims=" %%a in ('git remote get-url origin 2^>nul') do set EXISTING_REMOTE=%%a

if "%EXISTING_REMOTE%"=="" goto ask_url
echo [Step 4.2] existing remote: %EXISTING_REMOTE% >> "%LOG%"
echo [!] Remote already set: %EXISTING_REMOTE%

set REPLACE=
set /p REPLACE=Replace it? (y/N):
echo Step 4 replace answer: [%REPLACE%] >> "%LOG%"

if /i "%REPLACE%"=="y" goto do_replace
echo [v] Keeping existing remote
goto step5

:do_replace
git remote remove origin
echo [v] Old remote removed
goto ask_url

:ask_url
echo [Step 4.3] asking for repo URL >> "%LOG%"
echo.
echo Paste the GitHub repo URL you just created.
echo Supported formats:
echo   HTTPS: https://github.com/your-username/forest-island-daily.git
echo   SSH:   git@github.com:your-username/forest-island-daily.git
echo.

set REPO_URL=
set /p REPO_URL=Paste repo URL:
echo Step 4 URL answer: [%REPO_URL%] >> "%LOG%"

if "%REPO_URL%"=="" goto empty_url
git remote add origin "%REPO_URL%"
if errorlevel 1 goto add_remote_fail
echo [v] Remote added: %REPO_URL%
goto step5

:empty_url
echo [X] URL cannot be empty
goto fatal

:add_remote_fail
echo [X] Failed to add remote
goto fatal

REM ===========================================
REM Step 5 - commit + push
REM ===========================================
:step5
echo. & echo ----- Step 5 / 5: First commit and push -----
echo [Step 5.1] git add >> "%LOG%"

git add .
if errorlevel 1 goto add_fail

echo [Step 5.2] checking for existing commits >> "%LOG%"
git log --oneline >nul 2>nul
if errorlevel 1 goto first_commit

echo [Step 5.3] incremental commit path >> "%LOG%"
git diff --cached --quiet
if errorlevel 1 goto incr_commit
echo [!] No new changes
goto do_push

:first_commit
echo [Step 5.3] first commit path >> "%LOG%"
git commit -m "init: forest island daily"
if errorlevel 1 goto commit_fail
echo [v] First commit done
goto do_push

:incr_commit
for /f "tokens=2 delims==" %%a in ('"wmic os get LocalDateTime /value | findstr ="') do set DT=%%a
set TODAY=!DT:~0,4!-!DT:~4,2!-!DT:~6,2!
git commit -m "update: %TODAY%"
if errorlevel 1 goto commit_fail
echo [v] Incremental commit done
goto do_push

:do_push
echo [Step 5.4] git push >> "%LOG%"
git branch -M main 2>nul
echo.
echo Pushing to GitHub (first push may need login)...
echo.
git push -u origin main
if errorlevel 1 goto push_fail
echo [v] Push succeeded!
goto parse_url

:add_fail
echo [X] git add failed
goto fatal

:commit_fail
echo [X] git commit failed
goto fatal

:push_fail
echo.
echo [X] Push failed - browser will NOT open
echo.
echo Possible causes:
echo   1. Remote repo does not exist - create at https://github.com/new
echo   2. HTTPS auth - use Personal Access Token as password
echo      Generate: https://github.com/settings/tokens
echo   3. SSH - configure SSH key first
echo   4. Network - cannot reach github.com
goto fatal

REM ===========================================
REM Parse remote URL
REM ===========================================
:parse_url
echo [Step 6] parsing remote URL >> "%LOG%"

set REMOTE_URL=
for /f "delims=" %%a in ('git remote get-url origin') do set REMOTE_URL=%%a

set WEB=%REMOTE_URL%
set WEB=%WEB:.git=%
set WEB=%WEB:https://github.com/=%
set WEB=%WEB:git@github.com:=%

set OWNER=
set REPO=
for /f "tokens=1,2 delims=/" %%a in ("%WEB%") do (
    set OWNER=%%a
    set REPO=%%b
)

if "%OWNER%"=="" goto parse_fail
if "%REPO%"=="" goto parse_fail
goto success

:parse_fail
echo [X] Failed to parse remote URL: %REMOTE_URL%
goto fatal

REM ===========================================
REM Success
REM ===========================================
:success
echo.
echo ========================================
echo    Deploy succeeded! One last step.
echo ========================================
echo.
echo Parsed repo info:
echo   Owner: %OWNER%
echo   Repo : %REPO%
echo.
echo Please open the browser and enable GitHub Pages:
echo.
echo   1. Go to repo Pages settings:
echo      https://github.com/%OWNER%/%REPO%/settings/pages
echo.
echo   2. Under "Build and deployment":
echo      Source dropdown -^> select "GitHub Actions"
echo.
echo   3. Wait 1-2 minutes for auto-deploy
echo.
echo   4. After deploy, visit:
echo      https://%OWNER%.github.io/%REPO%/
echo.
echo Check deploy progress:
echo   https://github.com/%OWNER%/%REPO%/actions
echo.
echo -----------------------------------------
echo.
echo Daily usage from now on:
echo   - Every 08:00, Mira sends today.json to your Feishu
echo   - Save the attachment to data\today.json
echo   - Double-click push-today.bat
echo   - Website updates in 1-2 minutes
echo.
echo -----------------------------------------
echo.
echo Open GitHub Pages settings now?
echo   - type y then Enter -^> open browser
echo   - Enter or anything else  -^> do NOT open
set OPEN_NOW=
set /p OPEN_NOW=Your choice (y/N):
if /i "%OPEN_NOW%"=="y" goto do_open
echo [!] Browser not opened, copy the link above to access manually
goto end_ok

:do_open
start "" "https://github.com/%OWNER%/%REPO%/settings/pages"
echo [v] Opened Pages settings in browser
goto end_ok

REM ===========================================
REM Exit points
REM ===========================================
:fatal
echo === Deploy FAILED at %DATE% %TIME% === >> "%LOG%"
echo.
echo -----------------------------------------
echo Script stopped. Check messages above.
echo Full log: %CD%\deploy.log
echo -----------------------------------------
echo.
pause
exit /b 1

:end_ok
echo === Deploy completed at %DATE% %TIME% === >> "%LOG%"
echo.
echo -----------------------------------------
echo Script finished. Press any key to close.
echo Full log: %CD%\deploy.log
echo -----------------------------------------
echo.
pause
exit /b 0
