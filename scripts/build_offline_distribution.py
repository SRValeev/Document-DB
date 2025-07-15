#!/usr/bin/env python3
"""
Offline Distribution Builder for RAG Document Assistant v2.0
Creates a complete offline package for Windows servers without internet access
"""

import os
import sys
import shutil
import subprocess
import zipfile
import json
import tempfile
from pathlib import Path
from typing import List, Dict
import requests
from huggingface_hub import snapshot_download
import spacy

# Configuration for offline distribution
OFFLINE_CONFIG = {
    "version": "2.0.0-offline",
    "target_platform": "win_amd64",
    "python_version": "3.11",
    
    # Heavy models for better performance
    "models": {
        "embedding_model": "intfloat/multilingual-e5-large",
        "spacy_model": "ru_core_news_lg",
        "embedding_model_size": "2.24GB",
        "spacy_model_size": "560MB"
    },
    
    # Required components
    "components": [
        "python_packages",
        "ml_models", 
        "application_code",
        "configuration",
        "documentation",
        "installation_scripts"
    ]
}

class OfflineDistributionBuilder:
    """Builds offline distribution package"""
    
    def __init__(self, output_dir: str = "dist"):
        self.output_dir = Path(output_dir)
        self.build_dir = self.output_dir / "build"
        self.package_dir = self.build_dir / "rag-assistant-offline"
        
        # Create directories
        self.output_dir.mkdir(exist_ok=True)
        self.build_dir.mkdir(exist_ok=True)
        self.package_dir.mkdir(exist_ok=True)
        
        print(f"🏗️  Offline Distribution Builder v{OFFLINE_CONFIG['version']}")
        print(f"📦 Output directory: {self.output_dir.absolute()}")
    
    def create_directory_structure(self):
        """Create offline package directory structure"""
        print("\n📁 Creating directory structure...")
        
        directories = [
            "wheels",           # Python packages
            "models/embedding", # Embedding models
            "models/spacy",     # SpaCy models
            "app",              # Application code
            "config",           # Configuration templates
            "scripts",          # Installation scripts
            "docs",             # Documentation
            "tools",            # Additional tools
            "logs"              # Installation logs
        ]
        
        for dir_name in directories:
            dir_path = self.package_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"  ✓ Created: {dir_name}/")
    
    def download_python_packages(self):
        """Download all Python packages as wheels"""
        print("\n🐍 Downloading Python packages...")
        
        wheels_dir = self.package_dir / "wheels"
        
        # Read requirements
        with open("requirements.txt", "r", encoding="utf-8") as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        
        # Add platform-specific requirements
        offline_requirements = requirements + [
            "wheel>=0.41.0",
            "setuptools>=68.0.0",
            "pip>=23.2.0"
        ]
        
        print(f"📋 Found {len(offline_requirements)} packages to download")
        
        # Download wheels
        cmd = [
            sys.executable, "-m", "pip", "download",
            "--dest", str(wheels_dir),
            "--platform", OFFLINE_CONFIG["target_platform"],
            "--python-version", OFFLINE_CONFIG["python_version"],
            "--abi", "none",
            "--implementation", "cp",
            "--prefer-binary",
            "--no-deps"  # We'll handle dependencies separately
        ] + offline_requirements
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"  ✓ Downloaded packages to {wheels_dir}")
            
            # Count downloaded files
            wheel_count = len(list(wheels_dir.glob("*.whl")))
            tar_count = len(list(wheels_dir.glob("*.tar.gz")))
            print(f"  📦 {wheel_count} wheels, {tar_count} source packages")
            
        except subprocess.CalledProcessError as e:
            print(f"  ❌ Error downloading packages: {e}")
            print(f"  📝 stdout: {e.stdout}")
            print(f"  📝 stderr: {e.stderr}")
            return False
        
        return True
    
    def download_embedding_model(self):
        """Download embedding model from HuggingFace"""
        print(f"\n🤖 Downloading embedding model: {OFFLINE_CONFIG['models']['embedding_model']}")
        print(f"   Size: ~{OFFLINE_CONFIG['models']['embedding_model_size']}")
        
        model_dir = self.package_dir / "models" / "embedding"
        
        try:
            # Download model
            snapshot_download(
                repo_id=OFFLINE_CONFIG['models']['embedding_model'],
                local_dir=str(model_dir),
                local_dir_use_symlinks=False,
                resume_download=True
            )
            print(f"  ✓ Downloaded embedding model to {model_dir}")
            
            # Create model info file
            model_info = {
                "model_name": OFFLINE_CONFIG['models']['embedding_model'],
                "model_type": "sentence-transformer",
                "vector_size": 1024,  # e5-large has 1024 dimensions
                "local_path": "models/embedding",
                "downloaded_at": str(Path().absolute())
            }
            
            with open(model_dir / "model_info.json", "w", encoding="utf-8") as f:
                json.dump(model_info, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"  ❌ Error downloading embedding model: {e}")
            return False
    
    def download_spacy_model(self):
        """Download SpaCy model"""
        print(f"\n📝 Downloading SpaCy model: {OFFLINE_CONFIG['models']['spacy_model']}")
        print(f"   Size: ~{OFFLINE_CONFIG['models']['spacy_model_size']}")
        
        spacy_dir = self.package_dir / "models" / "spacy"
        
        try:
            # Download SpaCy model using pip
            cmd = [
                sys.executable, "-m", "pip", "download",
                "--dest", str(spacy_dir),
                f"https://github.com/explosion/spacy-models/releases/download/{OFFLINE_CONFIG['models']['spacy_model']}-3.7.0/{OFFLINE_CONFIG['models']['spacy_model']}-3.7.0.tar.gz"
            ]
            
            subprocess.run(cmd, check=True)
            print(f"  ✓ Downloaded SpaCy model to {spacy_dir}")
            
            # Create model info
            spacy_info = {
                "model_name": OFFLINE_CONFIG['models']['spacy_model'],
                "model_type": "spacy",
                "language": "ru",
                "components": ["tok2vec", "tagger", "parser", "senter", "ner", "attribute_ruler", "lemmatizer"],
                "local_path": "models/spacy",
                "downloaded_at": str(Path().absolute())
            }
            
            with open(spacy_dir / "spacy_info.json", "w", encoding="utf-8") as f:
                json.dump(spacy_info, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"  ❌ Error downloading SpaCy model: {e}")
            return False
    
    def copy_application_code(self):
        """Copy application source code"""
        print("\n📄 Copying application code...")
        
        app_dir = self.package_dir / "app"
        
        # Files and directories to copy
        items_to_copy = [
            "app/",
            "requirements.txt",
            "Dockerfile",
            "docker-compose.yml",
            ".env.example",
            "pytest.ini"
        ]
        
        for item in items_to_copy:
            src = Path(item)
            if src.is_file():
                dst = app_dir / src.name
                shutil.copy2(src, dst)
                print(f"  ✓ Copied file: {item}")
            elif src.is_dir():
                dst = app_dir / src.name
                shutil.copytree(src, dst, dirs_exist_ok=True)
                print(f"  ✓ Copied directory: {item}")
            else:
                print(f"  ⚠️  Not found: {item}")
        
        return True
    
    def create_offline_config(self):
        """Create offline-specific configuration"""
        print("\n⚙️  Creating offline configuration...")
        
        config_dir = self.package_dir / "config"
        
        # Offline configuration template
        offline_config = {
            "app_name": "RAG Document Assistant (Offline)",
            "version": OFFLINE_CONFIG["version"],
            "offline_mode": True,
            "debug": False,
            
            # Use local models
            "processing": {
                "embedding_model": "./models/embedding",
                "spacy_model": OFFLINE_CONFIG['models']['spacy_model'],
                "device": "cpu",
                "chunk_size": 1024,  # Larger chunks for better model
                "vector_size": 1024,  # e5-large vector size
                "batch_size": 16,     # Smaller batch for larger model
                "max_workers": 2      # Conservative for offline
            },
            
            # Database settings
            "database": {
                "host": "localhost",
                "port": 6333,
                "collection_name": "documents_offline",
                "vector_size": 1024
            },
            
            # Security (generate new keys during installation)
            "security": {
                "secret_key": "CHANGE_ME_DURING_INSTALLATION",
                "access_token_expire_minutes": 60,
                "max_login_attempts": 3
            },
            
            # Monitoring
            "monitoring": {
                "log_level": "INFO",
                "metrics_enabled": True,
                "log_format": "json"
            }
        }
        
        with open(config_dir / "offline_config.json", "w", encoding="utf-8") as f:
            json.dump(offline_config, f, indent=2)
        
        # Create .env template for offline mode
        env_template = """# RAG Document Assistant - Offline Configuration
APP_NAME="RAG Document Assistant (Offline)"
VERSION="2.0.0-offline"
DEBUG=false
OFFLINE_MODE=true

# Processing with heavy models
PROCESSING_EMBEDDING_MODEL=./models/embedding
PROCESSING_SPACY_MODEL=ru_core_news_lg
PROCESSING_DEVICE=cpu
PROCESSING_CHUNK_SIZE=1024
PROCESSING_VECTOR_SIZE=1024
PROCESSING_BATCH_SIZE=16
PROCESSING_MAX_WORKERS=2

# Database
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=documents_offline
QDRANT_VECTOR_SIZE=1024

# Security (will be generated during installation)
SECURITY_SECRET_KEY=GENERATE_DURING_INSTALL

# Monitoring
MONITORING_LOG_LEVEL=INFO
MONITORING_METRICS_ENABLED=true
MONITORING_LOG_FORMAT=json
"""
        
        with open(config_dir / ".env.offline", "w", encoding="utf-8") as f:
            f.write(env_template)
        
        print("  ✓ Created offline configuration")
        return True
    
    def create_installation_scripts(self):
        """Create installation scripts for Windows"""
        print("\n📜 Creating installation scripts...")
        
        scripts_dir = self.package_dir / "scripts"
        
        # Main PowerShell installer
        ps_installer = '''
# RAG Document Assistant v2.0 - Offline Installer
# PowerShell installation script for Windows Server

param(
    [string]$InstallPath = "C:\\RAGAssistant",
    [switch]$SkipPython = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Stop"
$VerbosePreference = if ($Verbose) { "Continue" } else { "SilentlyContinue" }

Write-Host "🚀 RAG Document Assistant v2.0 Offline Installer" -ForegroundColor Green
Write-Host "📍 Installation path: $InstallPath" -ForegroundColor Yellow

# Check if running as Administrator
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "❌ This script must be run as Administrator"
    exit 1
}

# Create installation directory
Write-Host "📁 Creating installation directory..."
New-Item -ItemType Directory -Force -Path $InstallPath | Out-Null
$AppPath = Join-Path $InstallPath "app"
$DataPath = Join-Path $InstallPath "data"
$LogsPath = Join-Path $InstallPath "logs"

New-Item -ItemType Directory -Force -Path $AppPath | Out-Null
New-Item -ItemType Directory -Force -Path $DataPath | Out-Null  
New-Item -ItemType Directory -Force -Path $LogsPath | Out-Null

# Check Python installation
Write-Host "🐍 Checking Python installation..."
try {
    $pythonVersion = python --version 2>$null
    Write-Host "  ✓ Found: $pythonVersion" -ForegroundColor Green
    
    # Check if Python is 3.11+
    $version = $pythonVersion -replace "Python ", ""
    $majorMinor = [version]($version.Split()[0])
    if ($majorMinor -lt [version]"3.11") {
        Write-Warning "⚠️  Python 3.11+ recommended, found $version"
    }
} catch {
    if ($SkipPython) {
        Write-Warning "⚠️  Python not found, but skipping installation as requested"
    } else {
        Write-Error "❌ Python 3.11+ is required. Please install Python first or use -SkipPython flag"
        exit 1
    }
}

# Create virtual environment
Write-Host "🔧 Creating virtual environment..."
$VenvPath = Join-Path $InstallPath "venv"
python -m venv $VenvPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "❌ Failed to create virtual environment"
    exit 1
}

# Activate virtual environment
$ActivateScript = Join-Path $VenvPath "Scripts\\Activate.ps1"
& $ActivateScript

# Install packages from wheels
Write-Host "📦 Installing Python packages..."
$WheelsPath = Join-Path $PSScriptRoot "..\\wheels"
python -m pip install --upgrade pip
python -m pip install --find-links $WheelsPath --no-index --force-reinstall (Get-ChildItem $WheelsPath -Filter "*.whl" | ForEach-Object { $_.Name })

if ($LASTEXITCODE -ne 0) {
    Write-Error "❌ Failed to install Python packages"
    exit 1
}

# Install SpaCy model
Write-Host "📝 Installing SpaCy model..."
$SpacyModelPath = Join-Path $PSScriptRoot "..\\models\\spacy"
$SpacyModel = Get-ChildItem $SpacyModelPath -Filter "*.tar.gz" | Select-Object -First 1
if ($SpacyModel) {
    python -m pip install $SpacyModel.FullName
    Write-Host "  ✓ Installed SpaCy model: ru_core_news_lg" -ForegroundColor Green
} else {
    Write-Warning "⚠️  SpaCy model not found"
}

# Copy application code
Write-Host "📄 Copying application code..."
$SourceApp = Join-Path $PSScriptRoot "..\\app"
Copy-Item -Recurse -Force "$SourceApp\\*" $AppPath

# Copy and configure environment
Write-Host "⚙️  Configuring environment..."
$ConfigPath = Join-Path $PSScriptRoot "..\\config"
Copy-Item "$ConfigPath\\.env.offline" "$InstallPath\\.env"

# Generate secret key
$SecretKey = [System.Web.Security.Membership]::GeneratePassword(64, 16)
$EnvContent = Get-Content "$InstallPath\\.env" -Raw
$EnvContent = $EnvContent -replace "GENERATE_DURING_INSTALL", $SecretKey
Set-Content "$InstallPath\\.env" $EnvContent

# Create service script
Write-Host "🔧 Creating service files..."
$ServiceScript = @"
@echo off
cd /d "$InstallPath"
call venv\\Scripts\\activate.bat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
"@

Set-Content "$InstallPath\\start_service.bat" $ServiceScript

# Create Windows Service (optional)
$NSSMPath = "C:\\nssm\\nssm.exe"
if (Test-Path $NSSMPath) {
    Write-Host "🔧 Installing Windows Service..."
    & $NSSMPath install "RAGAssistant" "$InstallPath\\start_service.bat"
    & $NSSMPath set "RAGAssistant" Description "RAG Document Assistant v2.0"
    & $NSSMPath set "RAGAssistant" Start SERVICE_AUTO_START
    Write-Host "  ✓ Service installed (use 'net start RAGAssistant' to start)" -ForegroundColor Green
}

# Installation summary
Write-Host ""
Write-Host "✅ Installation completed successfully!" -ForegroundColor Green
Write-Host "📍 Installation path: $InstallPath" -ForegroundColor Yellow
Write-Host "🌐 To start manually: cd '$InstallPath' && start_service.bat" -ForegroundColor Yellow
Write-Host "🔧 Service name: RAGAssistant (if NSSM available)" -ForegroundColor Yellow
Write-Host "📖 Access at: http://localhost:8000" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Start Qdrant vector database" -ForegroundColor White
Write-Host "2. Run: start_service.bat" -ForegroundColor White
Write-Host "3. Open browser: http://localhost:8000" -ForegroundColor White
'''
        
        with open(scripts_dir / "install.ps1", "w", encoding="utf-8") as f:
            f.write(ps_installer)
        
        # Batch installer wrapper
        batch_installer = '''@echo off
echo RAG Document Assistant v2.0 - Offline Installer
echo.

REM Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Error: This script must be run as Administrator
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

REM Run PowerShell installer
powershell.exe -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*

pause
'''
        
        with open(scripts_dir / "install.bat", "w", encoding="utf-8") as f:
            f.write(batch_installer)
        
        print("  ✓ Created PowerShell installer")
        print("  ✓ Created Batch installer wrapper")
        return True
    
    def copy_documentation(self):
        """Copy documentation files"""
        print("\n📚 Copying documentation...")
        
        docs_dir = self.package_dir / "docs"
        
        # Documentation files to copy
        doc_files = [
            "README_v2.md",
            "REBUILD_SUMMARY.md",
            "code_analysis.md"
        ]
        
        for doc_file in doc_files:
            if Path(doc_file).exists():
                shutil.copy2(doc_file, docs_dir / doc_file)
                print(f"  ✓ Copied: {doc_file}")
        
        # Create offline-specific README
        offline_readme = '''# RAG Document Assistant v2.0 - Offline Distribution

## 🔧 Offline Installation

This is an offline distribution package that includes all necessary components to run RAG Document Assistant on Windows servers without internet access.

### 📦 Package Contents

- **wheels/**: All Python packages as wheels
- **models/**: Heavy ML models for better performance
  - `intfloat/multilingual-e5-large` (2.24GB) - Advanced embedding model
  - `ru_core_news_lg` (560MB) - Large Russian language model
- **app/**: Complete application source code
- **config/**: Offline configuration templates
- **scripts/**: Installation scripts
- **docs/**: Documentation

### 🚀 Quick Installation

1. **Extract** this package to a temporary directory
2. **Run as Administrator**: `scripts\\install.bat`
3. **Follow** the installation prompts
4. **Start** the service

### 📋 Prerequisites

- Windows Server 2016+ or Windows 10+
- Python 3.11+ (will be checked during installation)
- 8GB+ RAM (recommended for large models)
- 10GB+ free disk space

### 🔧 Manual Installation

If automated installation fails:

```cmd
# 1. Create installation directory
mkdir C:\\RAGAssistant
cd C:\\RAGAssistant

# 2. Create virtual environment
python -m venv venv
venv\\Scripts\\activate

# 3. Install packages
pip install --find-links wheels --no-index --force-reinstall wheels/*.whl

# 4. Copy application
xcopy /E /I app\\* .

# 5. Configure environment
copy config\\.env.offline .env

# 6. Start application
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 🌐 Access

After installation, access the application at:
- **Web Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 📊 Heavy Models Performance

This offline distribution uses heavy models for enhanced performance:

| Model | Size | Performance Gain | Use Case |
|-------|------|------------------|----------|
| multilingual-e5-large | 2.24GB | +40% accuracy | Better embeddings |
| ru_core_news_lg | 560MB | +25% accuracy | Russian text processing |

### 🔧 Troubleshooting

**Common Issues:**

1. **Python not found**: Install Python 3.11+ and add to PATH
2. **Permission denied**: Run as Administrator
3. **Model loading fails**: Ensure 8GB+ RAM available
4. **Port 8000 busy**: Change port in .env file

**Log Files:**
- Application logs: `C:\\RAGAssistant\\logs\\`
- Installation log: Check PowerShell output

### 📞 Support

For technical support, refer to the documentation in `docs/` folder.
'''
        
        with open(docs_dir / "OFFLINE_README.md", "w", encoding="utf-8") as f:
            f.write(offline_readme)
        
        print("  ✓ Created offline documentation")
        return True
    
    def create_manifest(self):
        """Create distribution manifest"""
        print("\n📋 Creating distribution manifest...")
        
        # Calculate sizes
        total_size = 0
        component_sizes = {}
        
        for component in ["wheels", "models", "app", "config", "scripts", "docs"]:
            component_path = self.package_dir / component
            if component_path.exists():
                size = sum(f.stat().st_size for f in component_path.rglob('*') if f.is_file())
                component_sizes[component] = size
                total_size += size
        
        manifest = {
            "name": "RAG Document Assistant v2.0 Offline",
            "version": OFFLINE_CONFIG["version"],
            "build_date": str(Path().absolute()),
            "target_platform": OFFLINE_CONFIG["target_platform"],
            "python_version": OFFLINE_CONFIG["python_version"],
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "components": OFFLINE_CONFIG["components"],
            "component_sizes_mb": {k: round(v / 1024 / 1024, 2) for k, v in component_sizes.items()},
            "models": OFFLINE_CONFIG["models"],
            "installation": {
                "script": "scripts/install.ps1",
                "requirements": [
                    "Windows Server 2016+ or Windows 10+",
                    "Python 3.11+",
                    "8GB+ RAM",
                    "10GB+ disk space",
                    "Administrator privileges"
                ]
            }
        }
        
        with open(self.package_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        
        print(f"  ✓ Total package size: {manifest['total_size_mb']:.1f} MB")
        return True
    
    def create_archive(self):
        """Create final distribution archive"""
        print("\n📦 Creating distribution archive...")
        
        archive_name = f"rag-assistant-v{OFFLINE_CONFIG['version']}-offline-windows.zip"
        archive_path = self.output_dir / archive_name
        
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as zipf:
            for file_path in self.package_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(self.build_dir)
                    zipf.write(file_path, arcname)
                    if len(str(arcname)) % 100 == 0:  # Progress indicator
                        print(".", end="", flush=True)
        
        print()  # New line after progress dots
        
        # Archive info
        archive_size = archive_path.stat().st_size / 1024 / 1024
        print(f"  ✓ Created: {archive_name}")
        print(f"  📏 Archive size: {archive_size:.1f} MB")
        
        return archive_path
    
    def build_distribution(self):
        """Build complete offline distribution"""
        print("🚀 Starting offline distribution build...")
        
        steps = [
            ("Directory structure", self.create_directory_structure),
            ("Python packages", self.download_python_packages),
            ("Embedding model", self.download_embedding_model),
            ("SpaCy model", self.download_spacy_model),
            ("Application code", self.copy_application_code),
            ("Offline configuration", self.create_offline_config),
            ("Installation scripts", self.create_installation_scripts),
            ("Documentation", self.copy_documentation),
            ("Distribution manifest", self.create_manifest),
            ("Archive creation", self.create_archive)
        ]
        
        for step_name, step_func in steps:
            print(f"\n{'='*60}")
            print(f"🔄 {step_name}")
            print('='*60)
            
            try:
                result = step_func()
                if result is False:
                    print(f"❌ Failed: {step_name}")
                    return False
                    
            except Exception as e:
                print(f"❌ Error in {step_name}: {e}")
                return False
        
        print(f"\n{'='*60}")
        print("✅ Offline distribution build completed successfully!")
        print('='*60)
        print(f"📦 Package location: {self.output_dir.absolute()}")
        print("📋 Next steps:")
        print("  1. Copy the archive to your offline Windows server")
        print("  2. Extract the archive")
        print("  3. Run scripts/install.bat as Administrator")
        print("  4. Follow the installation prompts")
        
        return True


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build offline distribution for RAG Document Assistant")
    parser.add_argument("--output", "-o", default="dist", help="Output directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    try:
        builder = OfflineDistributionBuilder(args.output)
        success = builder.build_distribution()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n❌ Build cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Build failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()