import os
import logging
import concurrent.futures
from tqdm import tqdm
from utils.file_processor import FileProcessor
from utils.helpers import get_processed_files_list, add_to_processed_files

def process_single_file(args):
    config, file_path = args
    try:
        processor = FileProcessor(config)
        chunks = processor.process_file(file_path)
        return (file_path, chunks)
    except Exception as e:
        logging.error(f"Ошибка обработки {file_path}: {str(e)}")
        return (file_path, [])

def parallel_process(config):
    processor = FileProcessor(config)
    data_dir = config['paths']['data_dir']
    processed_files_path = config['paths']['processed_files']
    
    # Получаем список уже обработанных файлов
    processed_files = get_processed_files_list(processed_files_path)
    
    # Сбор новых файлов
    file_paths = []
    for root, _, files in os.walk(data_dir):
        for file in files:
            file_path = os.path.join(root, file)
            file_id = os.path.relpath(file_path, data_dir)
            if file.lower().endswith(('.pdf', '.doc', '.docx')) and file_id not in processed_files:
                file_paths.append(file_path)
    
    results = {}
    for file_path in tqdm(file_paths, desc="Обработка файлов"):
        _, chunks = process_single_file(processor, file_path)
        if chunks:  # Если файл успешно обработан
            file_id = os.path.relpath(file_path, data_dir)
            add_to_processed_files(processed_files_path, file_id)
            results[file_path] = chunks
    
    return results