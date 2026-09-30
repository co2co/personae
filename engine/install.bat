@echo off
setlocal

rem ============================================================
rem  my-st 依赖安装脚本
rem  作用：创建虚拟环境并安装 requirements.txt 中的依赖
rem  用法：双击本脚本，或命令行执行 install.bat
rem  说明：仅在迁移 / 首次部署时运行一次；依赖变更后重跑即可
rem        脚本位置无关，可解压到任意目录直接运行
rem ============================================================

set "ROOT=%~dp0"
set "VENV=%ROOT%venv"

title my-st 依赖安装

cd /d "%ROOT%" || (
    echo [错误] 无法进入引擎目录：%ROOT%
    pause
    exit /b 1
)

echo ========================================
echo   my-st 依赖安装
echo ========================================

rem ---- 探测 Python：优先 py -3，其次 python ----
set "PY="
py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "PY=py -3"
) else (
    python --version >nul 2>&1
    if not errorlevel 1 (
        set "PY=python"
    )
)
if not defined PY (
    echo [错误] 未找到 Python。请安装 Python 3.10+ 并加入 PATH，
    echo        或从 python.org / Microsoft Store 安装。
    pause
    exit /b 1
)
echo [信息] 使用 Python：%PY%

echo [操作] 创建虚拟环境：%VENV%
%PY% -m venv "%VENV%"
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
