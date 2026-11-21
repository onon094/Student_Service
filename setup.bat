@echo off
chcp 65001 >nul
cd /d "%~dp0"

set NO_PROXY=*
set no_proxy=*

if exist ".venv\Scripts\python.exe" goto :install_deps

echo [1/2] 创建虚拟环境...
python -m venv .venv
if errorlevel 1 goto :error

:install_deps
echo [2/2] 安装依赖...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

if not exist ".env" copy ".env.example" ".env" >nul

echo.
echo 安装完成。双击 run.bat 启动后端。
pause
exit /b 0

:error
echo.
echo 安装失败，请检查 Python 是否安装、网络是否可用。
pause
exit /b 1