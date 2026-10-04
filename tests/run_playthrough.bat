@echo off
setlocal

rem ============================================================
rem  群像弈（Personae） 走查运行器（落盘 markdown，无需 pytest）
rem  用法：
rem    run_playthrough.bat            -> 跑一局走查并保存
rem    run_playthrough.bat --keep     -> 跑完保留会话（可在 UI 继续）
rem    run_playthrough.bat --base URL -> 指定引擎基地址
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
    echo [错误] 未检测到测试虚拟环境（tests/venv），请先运行 install.bat。
    pause
    exit /b 1
)

echo ========================================
echo   群像弈（Personae） 走查（落盘 markdown）
echo   用法：run_playthrough.bat [--keep] [--base URL]
echo ========================================
"%PY%" run_playthrough.py %*

echo.
echo [完成] 走查结束。
pause
