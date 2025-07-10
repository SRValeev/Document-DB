#utils/helpers.py
import os
import re
import shutil
from typing import Optional
import yaml
import logging
import platform
import uuid
import numpy as np
from logging.handlers import RotatingFileHandler

def setup_logging(log_file="stdout.log"):
    """Настройка централизованного логирования"""
    try:
        # Создаем директорию для логов, если нужно
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # Конфигурация логгера
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        # Формат сообщений
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            encoding='utf-8'  # Добавляем кодировку
        )

        # Файловый обработчик с ротацией
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'  # Явно указываем кодировку
        )
        file_handler.setFormatter(formatter)

        # Консольный обработчик
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.WARNING)

        # Очистка старых обработчиков
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Добавление обработчиков
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        logger.info("Логгер успешно инициализирован")
        return True
    except Exception as e:
        print(f"CRITICAL: Не удалось настроить логирование: {str(e)}")
        return False

def windows_path(path):
    if platform.system() == 'Windows':
        return os.path.normpath(path)
    return path

def load_config(config_path="config.yaml"):
    try:
        with open(windows_path(config_path), 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            logging.info("Config loaded successfully")
            return config
    except Exception as e:
        logging.error(f"Error loading config: {str(e)}")
        raise

def normalize_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s.,:;!?()\-—–/]', '', text)
    return text.strip()

def create_dir(path):
    path = windows_path(path)
    if path and path != '' and not os.path.exists(path):
        os.makedirs(path)
        logging.info(f"Created directory: {path}")

def generate_unique_id():
    return str(uuid.uuid4())

def create_zero_vector(size):
    return np.zeros(size).tolist()

def get_processed_files_list(file_path):
    """Возвращает список уже обработанных файлов"""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f)
    return set()

def add_to_processed_files(file_path, processed_file):
    """Добавляет файл в список обработанных"""
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(processed_file + '\n')
    logging.info(f"Added to processed files: {processed_file}")

def clear_directory(dir_path: str, exclude: Optional[list] = None):
    """Безопасная очистка директории"""
    if not os.path.exists(dir_path):
        return
    
    exclude = exclude or []
    for filename in os.listdir(dir_path):
        if filename in exclude:
            continue
            
        file_path = os.path.join(dir_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            logging.warning(f"Не удалось удалить {file_path}: {str(e)}")