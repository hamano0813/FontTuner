@echo off
@chcp 65001 > nul

cd /d "%~dp0"

if exist .venv (
    call .venv\Scripts\activate
) else (
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r requirements.txt
)

set "files="

:loop
if "%~1"=="" goto run
set "files=%files% "%~1""
shift
goto loop

:run
python -B src\main.py %files%
goto end

:end

pause
