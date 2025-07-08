import os
import re
import yaml
import logging
import platform
import uuid
import numpy as np

def windows_path(path):
    if platform.system() == 'Windows':
        return os.path.normpath(path)
    return path

def setup_logging(log_file):
    if not log_file:
        # Настроим логирование в консоль, если путь не указан
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return

    log_file = windows_path(log_file)
    log_dir = os.path.dirname(log_file)
    
    # Создаем директорию только если путь содержит поддиректории
    if log_dir and log_dir != '':
        os.makedirs(log_dir, exist_ok=True)
    
    try:
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            encoding='utf-8'
        )
    except Exception as e:
        # Если не удалось создать файловый логгер, используем консольный
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        logging.error(f"Не удалось настроить файловое логирование: {str(e)}")

def load_config(config_path="config.yaml"):
    try:
        with open(windows_path(config_path), 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки конфигурации: {str(e)}")
        return {}

def normalize_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s.,:;!?()\-—–/]', '', text)
    return text.strip()

def create_dir(path):
    path = windows_path(path)
    if path and path != '' and not os.path.exists(path):
        os.makedirs(path)

def generate_unique_id():
    return str(uuid.uuid4())

def create_zero_vector(size):
    return np.zeros(size).tolist()