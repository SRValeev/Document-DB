import os
import logging
import concurrent.futures
from tqdm import tqdm
from utils.file_processor import FileProcessor
from utils.helpers import get_processed_files_list, add_to_processed_files
from datetime import datetime
import json

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
    output_dir = config['paths']['output_dir']  # Используем output_dir вместо processed_files
    
    # Создаем выходную директорию, если не существует
    os.makedirs(output_dir, exist_ok=True)
    
    # Сбор всех файлов
    file_paths = []
    for root, _, files in os.walk(data_dir):
        for file in files:
            if file.lower().endswith(('.pdf', '.doc', '.docx')):
                file_paths.append(os.path.join(root, file))
    
    # Многопоточная обработка
    results = {}
    num_workers = config['processing'].get('num_workers', 4)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            executor.submit(process_single_file, (config, fp)) 
            for fp in file_paths
        ]
        
        for future in tqdm(
            concurrent.futures.as_completed(futures), 
            total=len(futures), 
            desc="Параллельная обработка"
        ):
            file_path, chunks = future.result()
            results[file_path] = chunks
    
    # Сохраняем информацию о processed files
    processed_info = {
        "files": list(results.keys()),
        "timestamp": datetime.now().isoformat()
    }
    
    with open(os.path.join(output_dir, "processing_info.json"), 'w') as f:
        json.dump(processed_info, f)
    
    return results