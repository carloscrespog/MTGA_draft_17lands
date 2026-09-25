@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
	echo Python virtual environment not found.
	echo Create it with: python -m venv .venv
	echo Then install dependencies with: .venv\Scripts\python.exe -m pip install -r requirements.txt
	pause
	exit /b 1
)
call .venv\Scripts\activate.bat
python main.py
pause