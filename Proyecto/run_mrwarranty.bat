@echo off
cd /d "C:\Users\Komatsu\OneDrive - Komatsu Ltd\Documents\Python\002 Mr. Warranty\Proyecto"
python main.py >> logs\run_%date:~-4%%date:~4,2%%date:~7,2%.log 2>&1
