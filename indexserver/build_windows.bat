@echo off
setlocal
cd /d "%~dp0"
python -m PyInstaller --onefile --console --clean --add-data "web/explorer;web/explorer" --name nextBTC_IndexServer_V1.0.33 server.py
if errorlevel 1 exit /b 1
echo Build completed: dist\nextBTC_IndexServer_V1.0.33.exe
endlocal
