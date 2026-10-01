@echo off
setlocal

rem ============================================================
rem  ST-Lite 测试单元依赖安装
rem  作用：在 tests/ 下创建独立 venv 并安装 tests/requirements.txt
rem  说明：与引擎 engine/venv 完全独立，互不干扰。
rem       改测试依赖不会污染引擎运行环境，反之亦然。
rem ============================================================

set "ROOT=%~dp0"
set "VENV=%ROOT%venv"

title ST-Lite 测试依赖安装

cd /d "%ROOT%" || (
    echo [错误] 无法进入测试目录：%ROOT%
    pause
    exit /b 1
)

echo ========================================
echo   ST-Lite 测试依赖安装
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
    echo [错误] 未找到 Python。请安装 Python 3.10+ 并加入 PATH。
    pause
    exit /b 1
)
echo [信息] 使用 Python：%PY%

if not exist "%VENV%\Scripts\python.exe" (
    echo [操作] 创建虚拟环境：%VENV%
    %PY% -m venv "%VENV%"
    if errorlevel 1 (
        echo [失败] 虚拟环境创建失败。
        pause
        exit /b 1
    )
) else (
    echo [信息] 虚拟环境已存在，跳过创建：%VENV%
)

echo [操作] 升级 pip 并安装测试依赖...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 echo [警告] pip 升级失败，继续...
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [失败] 依赖安装失败，请检查网络连接。
    pause
    exit /b 1
)

echo ========================================
echo [完成] 测试依赖安装成功。可双击 run_tests.bat 运行测试。
echo ========================================
pause
