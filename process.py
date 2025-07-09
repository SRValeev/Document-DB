import os
import shutil
from typing import Dict, List
from tqdm import tqdm
from parallel_processor import parallel_process
from utils.file_processor import FileProcessor
from utils.helpers import load_config, setup_logging

def clear_data_directory(data_dir: str):
    """Очищает каталог data после обработки"""
    try:
        for filename in os.listdir(data_dir):
            file_path = os.path.join(data_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f'Не удалось удалить {file_path}. Причина: {e}')
    except Exception as e:
        print(f'Ошибка при очистке каталога data: {e}')

def main() -> Dict[str, List[str]]:
    """Основная функция обработки документов"""
    config = load_config()
    setup_logging(config['paths']['log_file'])
    output_dir = config['paths']['output_dir']
    data_dir = config['paths']['data_dir']
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Параллельная обработка файлов
    all_chunks = parallel_process(config)
    
    # Инициализация процессора файлов
    processor = FileProcessor(config)
    processed_files = []
    
    # Сохранение результатов
    for file_path, chunks in tqdm(all_chunks.items(), desc="Сохранение чанков"):
        output_file = os.path.join(
            output_dir, 
            f"{os.path.splitext(os.path.basename(file_path))[0]}.json"
        )
        processor.save_chunks(chunks, output_file)
        processed_files.append(file_path)
    
    # Создание глобального индекса
    processor.create_global_index(output_dir)
    
    # Очистка каталога data после успешной обработки
    clear_data_directory(data_dir)
    
    return {
        "processed_files": processed_files,
        "total_chunks": sum(len(chunks) for chunks in all_chunks.values())
    }