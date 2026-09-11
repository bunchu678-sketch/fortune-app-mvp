@echo off
setlocal
set "FORTUNE_TEST_PYTHON=%~dp0..\.venv\Scripts\python.exe"
if not exist "%FORTUNE_TEST_PYTHON%" (
  echo ERROR: Project Python not found. No installation was performed.
  echo See tests\README.md for an existing Python environment command.
  pause
  exit /b 3
)
"%FORTUNE_TEST_PYTHON%" -B "%~dp0check.py" %*
set "FORTUNE_TEST_STATUS=%ERRORLEVEL%"
echo.
pause
exit /b %FORTUNE_TEST_STATUS%
