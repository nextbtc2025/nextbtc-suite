@echo off
setlocal
cd /d "%~dp0"
python tools\run_full_acceptance.py %*
exit /b %errorlevel%
