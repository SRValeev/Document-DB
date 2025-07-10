[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

<#
.SYNOPSIS
    Установка RAG Document Assistant
.DESCRIPTION
    Скрипт установки всех зависимостей и настройки окружения
#>


# Настройки
$VENV_DIR = ".venv"
$QDRANT_VERSION = "v1.14.1"
$QDRANT_URL = "https://github.com/qdrant/qdrant/releases/download/$QDRANT_VERSION/qdrant-x86_64-pc-windows-msvc.zip"
$GHOSTSCRIPT_URL = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10051/gs10051w64.exe"

# Проверка Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python не установлен или не добавлен в PATH"
}

# Создание виртуального окружения
Write-Host "Создание виртуального окружения..." -ForegroundColor Cyan
python -m venv $VENV_DIR
if (-not (Test-Path "$VENV_DIR\Scripts\activate.ps1")) {
    throw "Ошибка создания виртуального окружения"
}

# Активация venv
Write-Host "Активация окружения..." -ForegroundColor Cyan
. "$VENV_DIR\Scripts\activate.ps1"

# Установка зависимостей
Write-Host "Установка Python-зависимостей..." -ForegroundColor Cyan
pip install --upgrade pip
pip install -r requirements\requirements.txt

# Установка spaCy моделей
Write-Host "Установка моделей spaCy..." -ForegroundColor Cyan
python -m spacy download ru_core_news_md
python -m spacy download ru_core_news_lg

# Установка Qdrant
Write-Host "Установка Qdrant..." -ForegroundColor Cyan
if (-not (Test-Path "qdrant\qdrant.exe")) {
    New-Item -ItemType Directory -Path "qdrant" -Force | Out-Null
    Invoke-WebRequest -Uri $QDRANT_URL -OutFile "qdrant\qdrant.zip"
    Expand-Archive -Path "qdrant\qdrant.zip" -DestinationPath "qdrant"
    Remove-Item "qdrant\qdrant.zip"
}

# Установка Ghostscript (для Camelot)
Write-Host "Установка Ghostscript..." -ForegroundColor Cyan
if (-not (Test-Path "C:\Program Files\gs")) {
    Invoke-WebRequest -Uri $GHOSTSCRIPT_URL -OutFile "gsinstaller.exe"
    Start-Process -Wait -FilePath "gsinstaller.exe" -ArgumentList "/S"
    Remove-Item "gsinstaller.exe"
}

# Установка Camelot
Write-Host "Установка Camelot..." -ForegroundColor Cyan
pip install camelot-py[base]
pip install opencv-python

# Создание директорий
Write-Host "Создание рабочих директорий..." -ForegroundColor Cyan
@("data", "processed", "temp", "qdrant\storage", "log") | ForEach-Object {
    New-Item -ItemType Directory -Path $_ -Force | Out-Null
}

Write-Host "`nУстановка завершена!`nДля запуска используйте: .\Scripts\startup.ps1" -ForegroundColor Green