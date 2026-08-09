@echo off
REM 重新生成 res/html/help.html（README.md -> 帮助页 HTML），需 pandoc
uv run build/make_help.py
pause
