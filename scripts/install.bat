@echo off
SETLOCAL

REM Проверка Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Ошибка: Python не установлен или не добавлен в PATH
    pause
    exit /b 1
)

REM Создание виртуального окружения
python -m venv .venv
if not exist ".venv\Scripts\activate.bat" (
    echo Ошибка создания виртуального окружения
    pause
    exit /b 1
)

REM Активация venv
call .venv\Scripts\activate.bat

REM Установка базовых зависимостей
pip install --upgrade pip
pip install -r requirements\requirements.txt

REM Установка spaCy моделей
echo Установка моделей spaCy...
python -m spacy download ru_core_news_md
python -m spacy download ru_core_news_lg

REM Установка Qdrant
echo Установка Qdrant...
mkdir qdrant 2>nul
cd qdrant
if not exist "qdrant.exe" (
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/qdrant/qdrant/releases/download/v1.14.1/qdrant-x86_64-pc-windows-msvc.zip' -OutFile 'qdrant.zip'"
    tar -xf qdrant.zip
    del qdrant.zip
)
cd ..

REM Установка Ghostscript (для Camelot)
if not exist "C:\Program Files\gs" (
    echo Установка Ghostscript...
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10051/gs10051w64.exe' -OutFile 'gsinstaller.exe'"
    gsinstaller.exe /S
    del gsinstaller.exe
)

REM Создание директорий
mkdir data 2>nul
mkdir processed 2>nul
mkdir temp 2>nul
mkdir qdrant\storage 2>nul

echo Установка завершена! Для запуска используйте scripts\start.bat
pause