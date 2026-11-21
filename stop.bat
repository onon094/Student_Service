@echo off
chcp 65001 >nul
title Stop Yuejiao Backend
echo.
echo  Stop Yuejiao Backend (port 8000)
echo  --------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1"
echo.
pause
