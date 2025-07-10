@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

:: Установка RAG Document Assistant для Windows
:: Версия 1.2 (оффлайн-совместимая)

:: Конфигурация
set VENV_DIR=.venv
set QDRANT_VERSION=v1.7.1
set QDRANT_URL=https://github.com/qdrant/qdrant/releases/download/%QDRANT_VERSION%/qdrant-x86_64-pc-windows-msvc.zip
set GHOSTSCRIPT_URL=https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10051/gs10051w64.exe

:: Проверка Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Ошибка: Python не установлен или не добавлен в PATH
    echo Установите Python 3.9+ и добавьте в PATH
    pause
    exit /b 1
)

:: Проверка архитектуры
set ARCH=64
if "%PROCESSOR_ARCHITECTURE%" == "x86" (
    set ARCH=32
    echo Предупреждение: 32-битная система, возможны проблемы с некоторыми моделями
)

:: Создание виртуального окружения
echo Создание виртуального окружения...
python -m venv %VENV_DIR%
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Ошибка создания виртуального окружения
    pause
    exit /b 1
)

:: Активация venv
call %VENV_DIR%\Scripts\activate.bat

:: Установка базовых зависимостей
echo Установка Python-зависимостей...
pip install --upgrade pip
if exist "requirements\requirements_offline" (
    pip install --no-index --find-links=requirements\requirements_offline -r requirements\requirements_offline\requirements.txt
) else (
    pip install -r requirements\requirements.txt
)

:: Установка моделей spaCy (оффлайн или онлайн)
echo Установка моделей spaCy...
if exist "models\ru_core_news_lg" (
    python -m spacy link models\ru_core_news_lg ru_core_news_lg --force
) else (
    python -m spacy download ru_core_news_lg
)

if exist "models\ru_core_news_md" (
    python -m spacy link models\ru_core_news_md ru_core_news_md --force
) else (
    python -m spacy download ru_core_news_md
)

:: Установка Qdrant
echo Установка Qdrant...
if not exist "qdrant\qdrant.exe" (
    if exist "qdrant-offline\qdrant-x86_64-pc-windows-msvc.exe" (
        mkdir qdrant 2>nul
        copy "qdrant-offline\qdrant-x86_64-pc-windows-msvc.exe" "qdrant\qdrant.exe"
    ) else (
        mkdir qdrant 2>nul
        powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%QDRANT_URL%' -OutFile 'qdrant\qdrant.zip'"
        tar -xf qdrant\qdrant.zip -C qdrant
        del qdrant\qdrant.zip
    )
)

:: Установка Ghostscript (для Camelot)
echo Установка Ghostscript...
if not exist "C:\Program Files\gs" (
    if exist "dependencies\gsinstaller.exe" (
        start /wait dependencies\gsinstaller.exe /S
    ) else (
        powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%GHOSTSCRIPT_URL%' -OutFile 'gsinstaller.exe'"
        start /wait gsinstaller.exe /S
        del gsinstaller.exe
    )
)

:: Установка Camelot и OpenCV (оффлайн)
echo Установка Camelot...
if exist "dependencies\python_packages" (
    pip install --no-index --find-links=dependencies\python_packages camelot-py[base] opencv-python
) else (
    pip install camelot-py[base] opencv-python
)

:: Создание директорий
echo Создание рабочих директорий...
mkdir data 2>nul
mkdir processed 2>nul
mkdir temp 2>nul
mkdir qdrant\storage 2>nul
mkdir log 2>nul
mkdir models 2>nul

:: Проверка установки
echo Проверка установки...
python -c "import spacy, camelot, sentence_transformers; print('Проверка завершена успешно')" || (
    echo Ошибка проверки зависимостей
    pause
    exit /b 1
)

echo.
echo ============================================
echo Установка завершена успешно!
echo.
echo Для запуска сервиса выполните:
echo   scripts\startup.bat
echo.
echo Для оффлайн-установки скопируйте на целевой ПК:
echo - Каталог models с NLP-моделями
echo - Каталог dependencies с системными пакетами
echo - Каталог qdrant-offline с бинарником Qdrant
echo ============================================
pause