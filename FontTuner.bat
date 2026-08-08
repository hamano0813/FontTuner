@echo off
@chcp 65001 > nul

cd /d "%~dp0"

if exist .venv (
    call .venv\Scripts\activate
) else (
    uv sync
    call .venv\Scripts\activate
)

set "files="

:loop
if "%~1"=="" goto run
set "files=%files% "%~1""
shift
goto loop

:run
python -B gui.py %files%
goto end

:end

pause
