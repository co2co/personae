@echo off
setlocal

rem ============================================================
rem  群像弈 启动脚本（引擎独立 venv）
rem  作用：检测端口占用 -> 占用则先 kill -> 用 engine/venv 启动 Flask
rem  前置：需先运行 install.bat 安装依赖（创建 engine/venv）
rem  停止：在窗口按 Ctrl+C
rem  说明：venv 位于 engine/venv，与测试单元 venv 完全独立。
rem ============================================================

set "PORT=5051"
set "HOST=0.0.0.0"
set "ROOT=%~dp0"
set "VENV=%ROOT%venv"

title 群像弈 服务 (端口 %PORT%)

cd /d "%ROOT%" || (
    echo [错误] 无法进入引擎目录：%ROOT%
    pause
    exit /b 1
)

echo ========================================
echo   群像弈 启动脚本
echo ========================================

if not exist "%VENV%\Scripts\python.exe" (
    echo [错误] 未检测到虚拟环境（engine/venv）。
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
rem 计算本机局域网 IP（取访问公网时的源地址），用于手机等设备的访问提示
for /f "delims=" %%a in (
    'powershell -NoProfile -Command "(Test-Connection -ComputerName 8.8.8.8 -Count 1 -ErrorAction SilentlyContinue).SourceAddress.IPAddress" 2^>nul'
) do set "LAN_IP=%%a"
if not defined LAN_IP set "LAN_IP=127.0.0.1"

echo ========================================
echo   正在启动 群像弈 服务
echo   本机访问：http://127.0.0.1:%PORT%
echo   局域网访问（手机/其他设备）：http://%LAN_IP%:%PORT%
echo   绑定地址：%HOST%:%PORT%
echo   按 Ctrl+C 停止服务
echo ========================================
set "FLASK_DEBUG=0"
"%VENV%\Scripts\python.exe" app.py

endlocal
