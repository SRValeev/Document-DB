@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8

echo Очистка временных файлов...
rmdir /s /q temp 2>nul
mkdir temp

echo Запуск Qdrant сервера...
start "" "qdrant\qdrant.exe" --storage-snapshot-interval-sec 60

echo Ожидание запуска Qdrant (10 сек)...
timeout /t 10 >nul

echo Запуск обработки документов...
python process.py

echo Загрузка данных в векторную БД...
python ingest.py

echo Запуск RAG-системы...
python query.py

pause