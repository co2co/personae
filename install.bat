@echo off
setlocal

rem ============================================================
rem  my-st 依赖安装脚本
rem  作用：创建虚拟环境并安装 requirements.txt 中的依赖
rem  用法：双击本脚本，或命令行执行 install.bat
rem  说明：仅在迁移 / 首次部署时运行一次；依赖变更后重跑即可
rem ============================================================

set "SYSTEM_PYTHON=C:\Users\co2co\AppData\Local\Programs\Python\Python312\python.exe"
set "ROOT=D:\codes\my-st"
set "VENV=%ROOT%\venv"

title my-st 依赖安装

cd /d "%ROOT%" || (
    echo [错误] 无法进入项目目录：%ROOT%
    pause
    exit /b 1
)

echo ========================================
echo   my-st 依赖安装
echo ========================================

if not exist "%SYSTEM_PYTHON%" (
    echo [错误] 未找到系统 Python：%SYSTEM_PYTHON%
    echo        请修改脚本中的 SYSTEM_PYTHON 路径，或把 Python 3.12 加入 PATH。
    pause
    exit /b 1
)

echo [操作] 创建虚拟环境：%VENV%
"%SYSTEM_PYTHON%" -m venv "%VENV%"
if errorlevel 1 (
    echo [失败] 虚拟环境创建失败。
    pause
    exit /b 1
)

echo [操作] 升级 pip 并安装依赖（首次较慢，请耐心等待）...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo [警告] pip 升级失败，继续尝试安装依赖...
)
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [失败] 依赖安装失败，请检查网络连接（如需代理请配置后重试）。
    pause
    exit /b 1
)

echo ========================================
echo [完成] 依赖安装成功。可双击 run.bat 启动服务。
echo ========================================
pause
