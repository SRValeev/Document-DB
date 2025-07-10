import os
import logging
import concurrent.futures
from tqdm import tqdm
from utils.file_processor import FileProcessor
from utils.helpers import load_config

def process_single_file(args):
    """Обработка одного файла в отдельном потоке"""
    config, file_path = args
    try:
        processor = FileProcessor(config)
        chunks = processor.process_file(file_path)
        return (file_path, chunks)
    except Exception as e:
        logging.error(f"Error processing {file_path}: {str(e)}", exc_info=True)
        return (file_path, [])

def parallel_process(config):
    """Параллельная обработка всех файлов в директории"""
    processor = FileProcessor(config)
    data_dir = config['paths']['data_dir']
    output_dir = config['paths']['output_dir']
    os.makedirs(output_dir, exist_ok=True)
    
    # Сбор всех файлов
    file_paths = []
    for root, _, files in os.walk(data_dir):
        for file in files:
            if file.lower().endswith(('.pdf', '.doc', '.docx')):
                file_path = os.path.join(root, file)
                file_paths.append(file_path)
    
    if not file_paths:
        logging.warning(f"No files found in {data_dir}")
        return {}
    
    results = {}
    num_workers = config['processing'].get('num_workers', 4)
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Подготовка задач
            tasks = [(config, fp) for fp in file_paths]
            
            # Используем tqdm для отображения прогресса
            with tqdm(total=len(tasks), desc="Обработка файлов") as pbar:
                futures = {
                    executor.submit(process_single_file, task): task
                    for task in tasks
                }
                
                for future in concurrent.futures.as_completed(futures):
                    file_path, chunks = future.result()
                    results[file_path] = chunks
                    pbar.update(1)
                    if chunks:
                        logging.info(f"Processed {file_path} -> {len(chunks)} chunks")
        
        logging.info(f"Parallel processing complete: {len(results)} files")
        return results
        
    except Exception as e:
        logging.error(f"Parallel processing failed: {str(e)}", exc_info=True)
        return {}

    # Сохранение информации о processed files
    try:
        processing_info = {
            "files": list(results.keys()),
            "timestamp": datetime.now().isoformat()
        }
        info_file = os.path.join(output_dir, "processing_info.json")
        with open(info_file, 'w') as f:
            json.dump(processing_info, f)
    except Exception as e:
        logging.error(f"Failed to save processing info: {str(e)}")

    return results