@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist logs mkdir logs
set PYTHONPATH=%~dp0src;%PYTHONPATH%
"%~dp0.venv\Scripts\python.exe" -m mr_warranty.pipelines.main %* >> "logs\run_%date:~-4%%date:~4,2%%date:~7,2%.log" 2>&1
set EC=%ERRORLEVEL%
echo [%date% %time%] ExitCode=%EC% >> "logs\run_%date:~-4%%date:~4,2%%date:~7,2%.log"
exit /b %EC%
