@echo off
cd /d "C:\Users\Komatsu\OneDrive - Komatsu Ltd\Documents\Python\002 Mr. Warranty\Proyecto"
set PYTHONPATH=%~dp0..\src;%PYTHONPATH%
python -m mr_warranty.pipelines.main %* >> logs\run_%date:~-4%%date:~4,2%%date:~7,2%.log 2>&1
if %errorlevel% neq 0 (
  echo [%date% %time%] Fallback a Proyecto/main.py shim >> logs\run_%date:~-4%%date:~4,2%%date:~7,2%.log 2>&1
  python main.py %* >> logs\run_%date:~-4%%date:~4,2%%date:~7,2%.log 2>&1
)
