@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements-dev.txt
if errorlevel 1 exit /b 1
python tools\run_full_acceptance.py --build-exe --browser %*
exit /b %errorlevel%
