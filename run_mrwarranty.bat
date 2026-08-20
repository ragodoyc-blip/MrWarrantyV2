@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0src;%PYTHONPATH%
python -m mr_warranty.pipelines.main %* >> logs\run_%date:~-4%%date:~4,2%%date:~7,2%.log 2>&1
