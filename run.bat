@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 系统代理未启动时 pip 会报 ProxyError；这里让 pip 直连
set NO_PROXY=*
set no_proxy=*

if not exist ".venv\Scripts\python.exe" goto :no_venv
if not exist ".env" copy ".env.example" ".env" >nul

echo.
echo  粤教服务后端
echo  ---------------------------------
echo  接口文档：http://localhost:8000/docs
echo  健康检查：http://localhost:8000/api/health
echo  按 Ctrl+C 停止
echo.

REM 直接用虚拟环境里的 Python，不依赖 activate.bat，避免 PATH 问题
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

echo.
echo 服务已退出。如果上面有报错，请把报错内容截图发给老师/AI。
pause
exit /b 0

:no_venv
echo.
echo [错误] 没有找到虚拟环境 .venv
echo 请先双击 setup.bat，或在当前目录执行：
echo   python -m venv .venv
echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
pause
exit /b 1