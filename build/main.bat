@echo off
rem FontTuner launcher: de-elevate to normal privilege if started as admin.
rem Windows UIPI blocks OLE file drag from Explorer into elevated processes,
rem which would break drag-to-import fonts in the editor.
cd /d "%~dp0"

rem Detect admin (net session succeeds only when elevated)
net session >nul 2>&1
if %errorlevel%==0 (
    rem Elevated: relaunch python at Basic User (0x20000) trust level
    runas /trustlevel:0x20000 "\"%~dp0.venv\Scripts\pythonw.exe\" -B \"%~dp0script\main.pyc\""
) else (
    rem Normal privilege: run directly
    .venv\Scripts\pythonw -B script\main.pyc
)
