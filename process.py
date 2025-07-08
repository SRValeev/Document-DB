import os
import logging
from tqdm import tqdm
from utils.helpers import setup_logging, load_config, create_dir
from parallel_processor import parallel_process

def main() -> int:
    """Основная функция обработки документов"""
    config = load_config()
    
    # Настройка логирования с проверкой
    log_file = config.get('paths', {}).get('log_file', '')
    setup_logging(log_file)
    
    output_dir = config.get('paths', {}).get('output_dir', 'processed')
    create_dir(output_dir)  # Гарантируем создание директории
    
    # Параллельная обработка файлов
    all_chunks = parallel_process(config)
    
    # Сохранение результатов
    from utils.file_processor import FileProcessor
    processor = FileProcessor(config)
    
    for file_path, chunks in all_chunks.items():
        output_file = os.path.join(
            output_dir, 
            f"{os.path.splitext(os.path.basename(file_path))[0]}.json"
        )
        processor.save_chunks(chunks, output_file)
    
    # Создание глобального индекса
    processor.create_global_index(output_dir)
    
    return len(all_chunks)  # Возвращаем количество обработанных файлов

if __name__ == "__main__":
    try:
        processed_files = main()
        print(f"Успешно обработано {processed_files} файлов")
    except Exception as e:
        logging.error(f"Ошибка обработки документов: {str(e)}")
        raise
