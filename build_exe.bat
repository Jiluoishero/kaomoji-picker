@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
)

%PYTHON_EXE% -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    %PYTHON_EXE% -m pip install pyinstaller
    if errorlevel 1 (
        echo Failed to install PyInstaller.
        pause
        exit /b 1
    )
)

%PYTHON_EXE% -m PyInstaller ^
    --noconfirm ^
    --windowed ^
    --onedir ^
    --name KaomojiPicker ^
    --icon "icon\icon.ico" ^
    --exclude-module PyQt5 ^
    --exclude-module PyQt6 ^
    --exclude-module PySide2 ^
    main.py

if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

copy /y "data.json" "dist\KaomojiPicker\data.json" >nul
if errorlevel 1 (
    echo Failed to copy data.json next to the exe.
    pause
    exit /b 1
)

if exist "dist\KaomojiPicker\icon" rmdir /s /q "dist\KaomojiPicker\icon"
xcopy /e /i /y "icon" "dist\KaomojiPicker\icon" >nul
if errorlevel 1 (
    echo Failed to copy icon assets next to the exe.
    pause
    exit /b 1
)

echo.
echo Build complete: dist\KaomojiPicker\KaomojiPicker.exe
echo Keep data.json and icon next to the exe.
pause

endlocal
