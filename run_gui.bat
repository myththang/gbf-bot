@echo off
title GBF Bot Launcher
cd /d "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python chua duoc cai dat hoac chua duoc them vao PATH!
        echo Vui long tai va cai dat Python tu python.org
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=py
    )
) else (
    set PYTHON_CMD=python
)

echo Dang khoi dong GBF Bot GUI bang %PYTHON_CMD%...
%PYTHON_CMD% gbf_gui.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Ung dung ket thuc voi loi (Code: %errorlevel%).
    pause
)
