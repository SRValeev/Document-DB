# Download Qdrant for offline distribution
# PowerShell script to download Qdrant vector database

param(
    [string]$OutputDir = "tools",
    [string]$QdrantVersion = "v1.7.4"
)

$ErrorActionPreference = "Stop"

Write-Host "📥 Downloading Qdrant $QdrantVersion for offline distribution..." -ForegroundColor Green

# Create output directory
$ToolsDir = Join-Path $OutputDir "qdrant"
New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null

# Qdrant download URLs
$QdrantUrls = @{
    "windows" = "https://github.com/qdrant/qdrant/releases/download/$QdrantVersion/qdrant-x86_64-pc-windows-msvc.zip"
    "docker" = "qdrant/qdrant:$QdrantVersion"
}

try {
    # Download Windows binary
    Write-Host "🔄 Downloading Qdrant Windows binary..."
    $ZipPath = Join-Path $ToolsDir "qdrant-windows.zip"
    Invoke-WebRequest -Uri $QdrantUrls["windows"] -OutFile $ZipPath -UseBasicParsing
    
    # Extract to subdirectory
    $ExtractPath = Join-Path $ToolsDir "windows"
    Expand-Archive -Path $ZipPath -DestinationPath $ExtractPath -Force
    Remove-Item $ZipPath
    
    Write-Host "  ✓ Downloaded and extracted Qdrant binary" -ForegroundColor Green
    
    # Create Qdrant configuration
    $QdrantConfig = @"
# Qdrant Configuration for Offline RAG Assistant
storage:
  storage_path: ./storage
  
service:
  http_port: 6333
  grpc_port: 6334
  enable_cors: true
  
cluster:
  enabled: false
  
telemetry_disabled: true

log_level: INFO
"@
    
    Set-Content -Path (Join-Path $ToolsDir "qdrant_config.yaml") -Value $QdrantConfig
    
    # Create startup script
    $StartupScript = @"
@echo off
echo Starting Qdrant Vector Database...
echo Configuration: qdrant_config.yaml
echo Web UI: http://localhost:6333/dashboard
echo.

cd /d "%~dp0"
windows\qdrant.exe --config-path qdrant_config.yaml

pause
"@
    
    Set-Content -Path (Join-Path $ToolsDir "start_qdrant.bat") -Value $StartupScript
    
    # Create installation info
    $QdrantInfo = @{
        "version" = $QdrantVersion
        "download_date" = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        "binary_path" = "windows/qdrant.exe"
        "config_file" = "qdrant_config.yaml"
        "startup_script" = "start_qdrant.bat"
        "web_ui" = "http://localhost:6333/dashboard"
        "api_port" = 6333
        "grpc_port" = 6334
    }
    
    $QdrantInfo | ConvertTo-Json -Depth 3 | Set-Content (Join-Path $ToolsDir "qdrant_info.json")
    
    Write-Host "✅ Qdrant offline package prepared successfully!" -ForegroundColor Green
    Write-Host "📍 Location: $ToolsDir" -ForegroundColor Yellow
    Write-Host "🚀 Start with: start_qdrant.bat" -ForegroundColor Yellow
    
} catch {
    Write-Error "❌ Failed to download Qdrant: $_"
    exit 1
}