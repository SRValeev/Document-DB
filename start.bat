@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo Очистка временных файлов...
rmdir /s /q temp 2>nul
mkdir temp

echo Запуск сервиса...
uvicorn main:app --host 0.0.0.0 --port 8000

pause