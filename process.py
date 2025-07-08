import os
import logging
from tqdm import tqdm
from utils.helpers import setup_logging, load_config
from parallel_processor import parallel_process

def main():
    config = load_config()
    setup_logging(config['paths']['log_file'])
    output_dir = config['paths']['output_dir']
    os.makedirs(output_dir, exist_ok=True)
    
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
    
    print(f"\nОбработано {len(all_chunks)} файлов. Результаты в {output_dir}")

if __name__ == "__main__":
    main()