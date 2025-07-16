# create_offline_package.py
import os
import subprocess
from pathlib import Path

# Создаем папку для хранения пакетов
MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)

# Основные зависимости из requirements.txt
DEPENDENCIES = [
    "fastapi==0.109.0",
    "uvicorn[standard]==0.27.0",
    "pydantic==2.5.3",
    "pydantic-settings==2.1.0",
    "qdrant-client==1.8.0",
    "redis==5.0.1",
    "pymupdf==1.23.7",
    "python-docx==1.1.0",
    "python-pptx==0.6.23",
    "openpyxl==3.1.2",
    "camelot-py[base]==0.11.0",
    "pytesseract==0.3.10",
    "pillow==10.1.0",
    "spacy==3.7.0",
    "sentence-transformers==2.2.2",
    "transformers==4.36.2",
    "torch==2.1.2",
    "nltk==3.8.1",
    "scikit-learn==1.3.2",
    "pyyaml==6.0.1",
    "tqdm==4.66.1",
    "tenacity==8.2.3",
    "python-multipart==0.0.6"
]

def download_packages():
    """Скачивает все пакеты в формате .whl"""
    for package in DEPENDENCIES:
        subprocess.run([
            "pip", "download",
            "--dest", str(MODELS_DIR),
            package
        ])

def download_model():
    """Скачивает модель multilingual-e5-large"""
    subprocess.run([
        "huggingface-cli", "download",
        "intfloat/multilingual-e5-large",
        "--revision", "main",
        "--cache-dir", str(MODELS_DIR)
    ])

if __name__ == "__main__":
    download_packages()
    download_model()