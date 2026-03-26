@echo off
title Recruitment Video Tool
cd /d "%~dp0"

set NO_PROXY=localhost,127.0.0.1
set no_proxy=localhost,127.0.0.1

:: Find Node.js if not in PATH (check common D/C drive locations)
where npm >nul 2>&1
if errorlevel 1 (
    for %%d in (C D E) do (
        if exist "%%d:\nodejs\npm.cmd"                    set "PATH=%%d:\nodejs;%PATH%"
        if exist "%%d:\Program Files\nodejs\npm.cmd"      set "PATH=%%d:\Program Files\nodejs;%PATH%"
        if exist "%%d:\Program Files (x86)\nodejs\npm.cmd" set "PATH=%%d:\Program Files (x86)\nodejs;%PATH%"
    )
)

:: Kill any process holding port 7860
powershell -command "Get-NetTCPConnection -LocalPort 7860 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo [1/2] Checking Python deps...
pip install -r requirements.txt -q >> startup.log 2>&1

echo [2/2] Checking Remotion deps...
if not exist "remotion\node_modules" (
    cd remotion
    npm install >> ..\startup.log 2>&1
    cd ..
)

echo.
echo Starting... open http://localhost:7860
echo Press Ctrl+C to stop
echo Log: %~dp0startup.log
echo.

python main.py >> startup.log 2>&1

echo.
echo === App stopped. Last 20 lines of startup.log ===
powershell -command "Get-Content startup.log -Tail 20"
pause
