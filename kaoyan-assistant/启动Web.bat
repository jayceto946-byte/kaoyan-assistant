@echo off
chcp 65001 >nul
title 考研助手 Web UI

:: 尝试用 PowerShell 启动（推荐，功能完整）
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0launch.ps1" web 8080

:: 如果 PowerShell 失败，fallback 到简单启动
if %ERRORLEVEL% NEQ 0 (
    echo [FALLBACK] PowerShell 启动失败，使用基础启动...
    call "%~dp0venv310\Scripts\activate.bat"
    python "%~dp0main.py" web --port 8080
    pause
)
