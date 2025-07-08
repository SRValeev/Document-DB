import os
import re
import yaml
import logging
import platform

def windows_path(path):
    """Конвертирует путь в Windows-формат"""
    if platform.system() == 'Windows':
        return os.path.normpath(path)
    return path

def setup_logging(log_file):
    log_file = windows_path(log_file)
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        encoding='utf-8'
    )

def load_config(config_path="config.yaml"):
    with open(windows_path(config_path), 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def normalize_text(text):
    # Удаление лишних пробелов и спецсимволов
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s.,:;!?()\-—–/]', '', text)
    return text.strip()

def create_dir(path):
    path = windows_path(path)
    if not os.path.exists(path):
        os.makedirs(path)