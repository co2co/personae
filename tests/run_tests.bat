@echo off
setlocal

rem ============================================================
rem  群像弈（Personae） 测试单元运行器
rem  用法：双击运行快测；或命令行追加 pytest 参数
rem    run_tests.bat              -> 快测（确定性单测，不调 LLM，秒级）
rem    run_tests.bat -m integration -> 完整走查（需引擎在运行 + 真实 LLM）
rem  说明：使用 tests/venv，与引擎 venv 完全独立。
rem ============================================================

set "ROOT=%~dp0"
set "VENV=%ROOT%venv"
set "PY=%VENV%\Scripts\python.exe"

cd /d "%ROOT%" || (
    echo [错误] 无法进入测试目录：%ROOT%
    pause
    exit /b 1
)

if not exist "%VENV%\Scripts\python.exe" (
    echo [错误] 未检测到测试虚拟环境（tests/venv）。
    echo        请先运行 install.bat 安装测试依赖。
    pause
    exit /b 1
)

echo ========================================
echo   群像弈（Personae） 测试
echo ========================================
"%PY%" -m pytest %*

echo.
echo [完成] 测试结束。
pause
