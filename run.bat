@echo off
setlocal

rem ============================================================
rem  my-st 启动脚本
rem  作用：检测端口占用 -> 占用则先 kill -> 用 venv 启动 Flask
rem  前置：需先运行 install.bat 安装依赖（创建 venv）
rem  停止：在窗口按 Ctrl+C
rem ============================================================

set "PORT=5051"
set "ROOT=D:\codes\my-st"
set "VENV=%ROOT%\venv"

title my-st 服务 (端口 %PORT%)

cd /d "%ROOT%" || (
    echo [错误] 无法进入项目目录：%ROOT%
    pause
    exit /b 1
)

echo ========================================
echo   my-st 启动脚本
echo ========================================

rem ---- 0. 检查虚拟环境 ----
if not exist "%VENV%\Scripts\python.exe" (
    echo [错误] 未检测到虚拟环境（%VENV%）。
    echo        请先运行 install.bat 安装依赖，再启动本脚本。
    pause
    exit /b 1
)

rem ---- 1. 检查端口是否被占用 ----
set "PID="
for /f "tokens=1,2,3,4,5" %%a in (
    'netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"'
) do set "PID=%%e"

if defined PID (
    echo [警告] 端口 %PORT% 已被进程 PID=%PID% 占用（可能是上次未释放的服务）。
    echo [操作] 正在关闭该进程...
    taskkill /F /PID %PID% >nul 2>&1
    if errorlevel 1 (
        echo [失败] 无法关闭 PID=%PID%，请手动结束后重试。
        pause
        exit /b 1
    )
    echo [完成] 已关闭占用进程，等待端口释放...
    timeout /t 2 /nobreak >nul
) else (
    echo [信息] 端口 %PORT% 空闲。
)

rem ---- 2. 启动服务 ----
echo ========================================
echo   正在启动 my-st 服务
echo   访问地址：http://127.0.0.1:%PORT%
echo   按 Ctrl+C 停止服务
echo ========================================
set "FLASK_DEBUG=0"
"%VENV%\Scripts\python.exe" app.py

endlocal
