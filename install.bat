@echo off
chcp 65001 > nul 2>&1
setlocal enabledelayedexpansion

:: RAG Document Assistant Windows Installation
:: Version 1.2 (offline-compatible)

:: Configuration
set VENV_DIR=.venv
set QDRANT_VERSION=v1.7.1
set QDRANT_URL=https://github.com/qdrant/qdrant/releases/download/%QDRANT_VERSION%/qdrant-x86_64-pc-windows-msvc.zip
set GHOSTSCRIPT_URL=https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10051/gs10051w64.exe

:: Check Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not added to PATH
    echo Please install Python 3.9+ and add to PATH
    pause
    exit /b 1
)

:: Check architecture
set ARCH=64
if "%PROCESSOR_ARCHITECTURE%" == "x86" (
    set ARCH=32
    echo [!] Warning: 32-bit system, possible issues with some models
)

:: Create virtual environment
echo [*] Creating virtual environment...
python -m venv %VENV_DIR%
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)

:: Активация venv
call %VENV_DIR%\Scripts\activate.bat

:: Install basic dependencies
echo [*] Installing Python dependencies...
pip install --upgrade pip
if exist "requirements\requirements_offline" (
    pip install --no-index --find-links=requirements\requirements_offline -r requirements\requirements_offline\requirements.txt
) else (
    pip install -r requirements\requirements.txt
)

:: Install spaCy models (offline or online)
echo [*] Installing spaCy models...
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

:: Install Qdrant
echo [*] Installing Qdrant...
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

:: Install Ghostscript (for Camelot)
echo [*] Installing Ghostscript...
if not exist "C:\Program Files\gs" (
    if exist "dependencies\gsinstaller.exe" (
        start /wait dependencies\gsinstaller.exe /S
    ) else (
        powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%GHOSTSCRIPT_URL%' -OutFile 'gsinstaller.exe'"
        start /wait gsinstaller.exe /S
        del gsinstaller.exe
    )
)

:: Install Camelot and OpenCV (offline)
echo [*] Installing Camelot...
if exist "dependencies\python_packages" (
    pip install --no-index --find-links=dependencies\python_packages camelot-py[base] opencv-python
) else (
    pip install camelot-py[base] opencv-python
)

:: Create directories
echo [*] Creating working directories...
mkdir data 2>nul
mkdir processed 2>nul
mkdir temp 2>nul
mkdir qdrant\storage 2>nul
mkdir log 2>nul
mkdir models 2>nul

:: Check installation
echo [*] Checking installation...
python -c "import spacy, camelot, sentence_transformers; print('Check completed successfully')" || (
    echo [ERROR] Dependencies check failed
    pause
    exit /b 1
)

echo.
echo ============================================
echo [SUCCESS] Installation completed successfully!
echo.
echo To start the service run:
echo   scripts\startup.bat
echo.
echo For offline installation copy to target PC:
echo - models directory with NLP models
echo - dependencies directory with system packages
echo - qdrant-offline directory with Qdrant binary
echo ============================================
pause