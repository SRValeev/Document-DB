import os
import yaml
import logging
from tqdm import tqdm
from utils.file_processor import FileProcessor
from utils.helpers import setup_logging, load_config

def main():
    config = load_config()
    print(f"\n{config['paths']['log_file']}")
    setup_logging(config['paths']['log_file'])
    
    processor = FileProcessor(config)
    data_dir = config['paths']['data_dir']
    output_dir = config['paths']['output_dir']
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Обработка всех файлов в каталоге
    processed_files = []
    for root, _, files in os.walk(data_dir):
        for file in tqdm(files, desc="Обработка документов"):
            if file.lower().endswith(('.pdf', '.doc', '.docx')):
                file_path = os.path.join(root, file)
                try:
                    chunks = processor.process_file(file_path)
                    output_file = os.path.join(
                        output_dir, 
                        f"{os.path.splitext(file)[0]}.json"
                    )
                    processor.save_chunks(chunks, output_file)
                    processed_files.append(file_path)
                except Exception as e:
                    logging.error(f"Ошибка обработки {file_path}: {str(e)}")
    
    # Создание единого индекса
    processor.create_global_index(output_dir)
    
    print(f"\nОбработано {len(processed_files)} файлов. Результаты в {output_dir}")

if __name__ == "__main__":
    main()