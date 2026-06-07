@echo off
cd /d "%~dp0"
echo Installing dependencies...
python -m pip install -r requirements.txt --quiet 2>nul

echo Starting Ollama...
start "" ollama serve
timeout /t 3 /nobreak > nul

cd /d "%~dp0server"
python main_chat.py --web
pause
