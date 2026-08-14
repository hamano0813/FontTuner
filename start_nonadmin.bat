@echo off
rem Dev launcher: run FontTuner (src/main.py) at normal (non-admin) privilege.
rem Windows UIPI blocks OLE file drag from Explorer into elevated processes,
rem which would break drag-to-import fonts. Works from any terminal, even if
rem Windows Terminal defaults to admin.
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
runas /trustlevel:0x20000 "\"%~dp0.venv\Scripts\python.exe\" -B \"%~dp0src\main.py\""
