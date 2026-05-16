@echo off
setlocal
title Aphrodite Tweaks Pro - Builder

echo ================================================
echo Aphrodite Tweaks Pro v3.0.0 - Build Script
echo ================================================
echo.

REM ---- Pick python.exe ----
echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python not found. Install from python.org and tick "Add to PATH".
        pause
        exit /b 1
    )
    set PY=python3
) else (
    set PY=python
)

REM ---- Ensure pip ----
echo Checking pip...
%PY% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pip not found. Run:  %PY% -m ensurepip --upgrade
    pause
    exit /b 1
)

REM ---- Install required deps ----
echo.
echo Installing dependencies (customtkinter, pyinstaller)...
%PY% -m pip install --upgrade pip --quiet
%PY% -m pip install --upgrade --quiet customtkinter pyinstaller
if errorlevel 1 (
    echo.
    echo First attempt failed - retrying without --quiet to show full output...
    %PY% -m pip install --upgrade customtkinter pyinstaller
)
%PY% -c "import customtkinter, PyInstaller; print('  customtkinter', customtkinter.__version__); print('  pyinstaller ', PyInstaller.__version__)" 2>nul
if errorlevel 1 (
    echo ERROR: Failed to install dependencies. Check your internet connection.
    pause
    exit /b 1
)

REM ---- Admin check (just a friendly notice) ----
net session >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Not running as Administrator.
    echo           The BUILD itself does NOT need admin, but the resulting
    echo           EXE must be run as Administrator to apply most tweaks.
    echo.
)

echo ================================================
echo Building EXE  (one-file, windowed)
echo This may take 1-3 minutes the first time...
echo ================================================
echo.

REM Clean previous artefacts to avoid stale specs
if exist AphroditeTweaksPro.exe del /q AphroditeTweaksPro.exe
if exist build rmdir /s /q build
if exist AphroditeTweaksPro.spec del /q AphroditeTweaksPro.spec

%PY% -m PyInstaller ^
    --onefile ^
    --noconfirm ^
    --windowed ^
    --clean ^
    --name AphroditeTweaksPro ^
    --collect-all customtkinter ^
    --hidden-import=tkinter ^
    --distpath . ^
    --workpath build ^
    --specpath . ^
    aphrodite_tweaks_pro.py

if exist "AphroditeTweaksPro.exe" (
    echo.
    echo ================================================
    echo BUILD SUCCESS!
    echo Output: %CD%\AphroditeTweaksPro.exe
    echo ================================================
    echo.
    echo NEXT STEPS:
    echo   1. Right-click AphroditeTweaksPro.exe
    echo   2. Choose "Run as administrator"
    echo   3. Optionally create a System Restore Point from the app
    echo.
) else (
    echo.
    echo BUILD FAILED - scroll up to read the PyInstaller errors.
    echo.
)

pause
endlocal
