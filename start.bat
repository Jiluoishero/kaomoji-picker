@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
)

%PYTHON_EXE% -c "import webview, keyboard, pyperclip, win32gui, win32api, win32con, pystray, PIL" >nul 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    %PYTHON_EXE% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
)

start "" %PYTHON_EXE% "%~dp0main.py"
endlocal
