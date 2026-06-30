@echo off
set "APP_DIR=%~dp0"
set "PYTHON=C:\Users\bunch\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "NODE=C:\Users\bunch\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"

cd /d "%APP_DIR%"

start "fortune-api" /MIN "%PYTHON%" "backend\server.py"
timeout /t 2 /nobreak >nul

start "fortune-next" /MIN "%NODE%" "node_modules\next\dist\bin\next" dev -H 127.0.0.1 -p 3000
timeout /t 8 /nobreak >nul

start "" "http://127.0.0.1:3000"
