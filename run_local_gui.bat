@echo off
echo ======================================================
echo INFINITESOL AI CONTENT FACTORY - LOCAL CONTROL CENTER
echo ======================================================
echo.
echo [1/2] Checking Dependencies...
python -m pip install -r requirements.txt --quiet
echo [2/2] Launching GUI Dashboard...
python local_automation_gui.py
echo.
echo Process terminated.
pause
