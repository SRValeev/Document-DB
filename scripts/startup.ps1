<#
.SYNOPSIS
    Запуск RAG Document Assistant
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Настройки
$QDRANT_PORT = 6333
$UVICORN_PORT = 8000

# Проверка Qdrant
if (-not (Test-Path "qdrant\qdrant.exe")) {
    Write-Host "Ошибка: Qdrant не установлен. Сначала выполните install.ps1" -ForegroundColor Red
    exit 1
}

# Проверка виртуального окружения
if (-not (Test-Path ".venv\Scripts\activate.ps1")) {
    Write-Host "Ошибка: Виртуальное окружение не найдено" -ForegroundColor Red
    exit 1
}

# Очистка временных файлов
Write-Host "Очистка временных файлов..." -ForegroundColor Cyan
Remove-Item -Path "temp\*" -Force -Recurse -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path "temp" -Force | Out-Null

# Запуск Qdrant в отдельном окне
Write-Host "Запуск Qdrant..." -ForegroundColor Cyan
Start-Process -NoNewWindow -FilePath "qdrant\qdrant.exe" -ArgumentList "--storage-snapshot-interval-sec 60"

# Ожидание старта Qdrant
$qdrantReady = $false
$attempts = 0
while (-not $qdrantReady -and $attempts -lt 10) {
    try {
        $response = Invoke-WebRequest "http://localhost:$QDRANT_PORT/" -UseBasicParsing -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $qdrantReady = $true
        }
    } catch {
        Start-Sleep -Seconds 3
        $attempts++
    }
}

if (-not $qdrantReady) {
    Write-Host "Ошибка: Qdrant не запустился" -ForegroundColor Red
    exit 1
}

# Активация venv и запуск сервиса
Write-Host "Запуск сервиса..." -ForegroundColor Cyan
. ".venv\Scripts\activate.ps1"
uvicorn main:app --host 0.0.0.0 --port $UVICORN_PORT

Write-Host "Сервис остановлен" -ForegroundColor Yellow