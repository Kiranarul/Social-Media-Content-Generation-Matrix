@echo off
echo Starting AI Content Generation Matrix...
:: Check if python is in PATH
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python is not installed or not added to your PATH.
    pause
    exit /b
)

python ai_engine.py
echo.
echo Process finished.
pause
