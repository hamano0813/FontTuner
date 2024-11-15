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

:loop
if "%~1"=="" goto end
python -B src\main.py "%~1"
shift
goto loop

:end
pause
