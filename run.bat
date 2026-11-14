@echo off
setlocal

rem ============================================================
rem  Personae - repo-root launcher and self-check panel
rem
rem  Why this file exists: engine\run.bat assumes engine\venv already
rem  exists and works. This wrapper repairs the venv when it is missing
rem  or broken, verifies the install, then hands over to engine\run.bat.
rem  The broken-venv case is the real one: after the repo is moved or
rem  renamed, engine\venv survives but its pyvenv.cfg points at a Python
rem  that no longer exists, so python.exe dies with "No Python at ..."
rem  or "Unable to create process". Testing for the file cannot see that,
rem  so step 2 runs the interpreter instead of looking at it.
rem
rem  Usage:
rem    run.bat                self-check, then start the engine (5051)
rem    run.bat check          self-check only, no server, no port used
rem    run.bat check nopause  same, non-interactive (script friendly)
rem    run.bat deps-dev     install requirements-dev.txt (pytest) + check
rem
rem  Notes:
rem    - ASCII only on purpose: a UTF-8 .bat breaks under the GBK
rem      console code page. Do not put non-ASCII text in this file.
rem    - venv repair refuses to run while the engine is listening on
rem      5051: moving or rewriting a venv under a live process breaks
rem      lazy imports in that process.
rem    - package.py only archives engine/, so this file is dev-only and
rem      never ships in the release zip.
rem ============================================================

set "ROOT=%~dp0"
set "ENGINE=%ROOT%engine"
set "VENV=%ENGINE%\venv"
set "PYEXE=%VENV%\Scripts\python.exe"
set "PORT=5051"
set "MODE=start"
set "PAUSE_ON_EXIT=1"
set "SMOKE="
if /i "%~1"=="check" set "MODE=check"
if /i "%~1"=="deps-dev" set "MODE=devdeps"
if /i "%~2"=="nopause" set "PAUSE_ON_EXIT="

title Personae self-check [%MODE%]

cd /d "%ENGINE%" 2>nul
if errorlevel 1 (
    echo [error] engine directory not found: %ENGINE%
    goto fail
)

echo ========================================
echo   Personae self-check [%MODE%]
echo ========================================

rem ---- 1. Locate a Python: py -3 first, then python on PATH ----
set "PY="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY=python"
)

rem ---- 2. venv: must exist, start, and carry its dependencies ----
if not exist "%PYEXE%" goto bootstrap

"%PYEXE%" -c "import sys" >nul 2>&1
if errorlevel 1 goto venv_stale

"%PYEXE%" -c "import flask, requests" >nul 2>&1
if not errorlevel 1 goto venv_ready

call :port_guard
if errorlevel 1 goto fail
echo [warn] engine\venv runs but flask/requests are missing.
echo [warn] reinstalling dependencies into the existing venv.
goto pip_install

:venv_stale
call :port_guard
if errorlevel 1 goto fail
echo [warn] engine\venv exists but its python cannot start.
echo [warn] stale venv: pyvenv.cfg likely points at a Python that moved.
if not defined PY (
    echo [error] no Python found to rebuild engine\venv with.
    echo         Install Python 3.10+ and make sure py or python is on PATH.
    goto fail
)
set "OLDVENV=%VENV%.stale"
if exist "%OLDVENV%" set "OLDVENV=%VENV%.stale%RANDOM%"
move "%VENV%" "%OLDVENV%" >nul 2>&1
if errorlevel 1 (
    echo [error] cannot move engine\venv aside - files inside are in use.
    echo         Close any process running out of engine\venv, then retry.
    goto fail
)
echo [info] old venv kept as %OLDVENV% - delete it once the new one works.

:bootstrap
if not defined PY (
    echo [error] engine\venv is missing and no Python was found.
    echo         Install Python 3.10+ and make sure py or python is on PATH.
    goto fail
)
echo [info] creating engine\venv with: %PY%
%PY% -m venv "%VENV%"
if errorlevel 1 (
    echo [error] venv creation failed.
    goto fail
)

:pip_install
"%PYEXE%" -m pip install --upgrade pip
echo [info] installing engine\requirements.txt ...
"%PYEXE%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [error] dependency install failed. Check network or proxy, then retry.
    goto fail
)

:venv_ready

rem ---- 2b. dev dependencies (opt-in): only for running the test suite ----
if /i "%MODE%"=="devdeps" (
    echo [info] installing engine\requirements-dev.txt ...
    "%PYEXE%" -m pip install -r requirements-dev.txt
    if errorlevel 1 (
        echo [error] dev dependency install failed. Check network or proxy, then retry.
        goto fail
    )
)

rem ---- 3. Build stamp: VERSION line 1 plus git HEAD/branch ----
rem VERSION is read with for /f on purpose: set /p would eat a leading
rem zero and print a prompt prefix when redirected.
set "ENG_VER=n/a"
for /f "usebackq delims=" %%v in ("VERSION") do set "ENG_VER=%%v"
set "GITINFO=n/a"
set "GITBRANCH=n/a"
where git >nul 2>&1
if not errorlevel 1 (
    for /f "usebackq delims=" %%g in (`git -C "%ROOT%." rev-parse --short HEAD`) do set "GITINFO=%%g"
    for /f "usebackq delims=" %%b in (`git -C "%ROOT%." rev-parse --abbrev-ref HEAD`) do set "GITBRANCH=%%b"
)

echo ========================================
echo   Build
echo ========================================
echo [build] version   %ENG_VER%
echo [build] git head  %GITINFO% ^(%GITBRANCH%^)

rem ---- 4. Runtime: python / flask / requests importable ----
rem Every -c payload below stays pure ASCII. A tag with CJK characters
rem inside cmd.exe can reach python as U+FFFD and then blow up with
rem UnicodeEncodeError on the gbk stdout - a self-check failing on its
rem own label instead of on the install.
"%PYEXE%" -c "import sys, importlib.metadata as m;print('[env]  python ' + sys.version.split()[0] + ' | flask ' + m.version('flask') + ' | requests ' + m.version('requests'))"
if errorlevel 1 (
    echo [error] runtime check failed - engine\venv may be incomplete.
    echo         Delete engine\venv and run this script again.
    goto fail
)

rem ---- 5. Data layer: modules import and counts read ----
"%PYEXE%" -c "import store, memory;print('[data] characters=' + str(len(store.list_characters())) + ' | worlds=' + str(len(store.list_worlds())) + ' | sessions=' + str(len(memory.list_sessions())))"
if errorlevel 1 (
    echo [error] data modules failed - local data may be unreadable.
    goto fail
)

rem ---- 6. LLM endpoint as configured (informational, never fatal) ----
"%PYEXE%" -c "import json;d=json.load(open('data/config.json',encoding='utf-8'));print('[llm]  base_url=' + (d.get('base_url') or '(unset)') + ' | model=' + (d.get('model') or '(unset)'))"

rem ---- 7. Endpoint smoke via Flask test_client: no server, no port ----
echo [smoke] endpoint smoke test via test_client ^(no server, no port^):
"%PYEXE%" -c "import sys, app as eng; c=eng.app.test_client(); eps=('/', '/api/config', '/api/characters', '/api/worlds', '/api/sessions', '/docs/worldbook'); codes=[(p, c.get(p).status_code) for p in eps]; [print('        ' + p + ' -> ' + str(n)) for p, n in codes]; sys.exit(0 if all(n == 200 for _, n in codes) else 1)"
if errorlevel 1 (
    echo [warn] at least one endpoint did not return 200.
    set "SMOKE=1"
) else (
    echo [smoke] all six endpoints returned 200.
)

if /i "%MODE%"=="check" goto check_done
if /i "%MODE%"=="devdeps" goto check_done

rem ---- 8. Hand over to engine\run.bat: port check and LAN URL ----
echo ========================================
echo   Handing over to engine\run.bat
echo ========================================
call "%ENGINE%\run.bat"
endlocal & exit /b 0

:check_done
echo ========================================
if defined SMOKE (
    echo [fail] self-check found endpoint errors. Server not started.
    goto fail
)
echo [done] self-check passed. Server not started.
echo ========================================
if defined PAUSE_ON_EXIT pause
endlocal & exit /b 0

rem ---- subroutine: refuse venv surgery while the engine is up ----
:port_guard
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 exit /b 0
echo [error] something is listening on port %PORT% - the engine is running.
echo         Repairing engine\venv under a live process breaks its lazy
echo         imports. Stop the engine, then run this script again.
exit /b 2

:fail
if defined PAUSE_ON_EXIT pause
endlocal & exit /b 1
