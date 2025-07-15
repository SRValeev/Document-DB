@echo off
chcp 65001 > nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo [*] Clearing temporary files...
rmdir /s /q temp 2>nul
mkdir temp

echo [*] Starting service...
uvicorn main:app --host 0.0.0.0 --port 8000

pause