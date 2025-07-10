import asyncio
import os
import shutil
import json
import logging
from tqdm import tqdm
from utils.parallel_processor import parallel_process
from utils.file_processor import FileProcessor
from utils.helpers import load_config
from utils.ingest import main as ingest_main

logger = logging.getLogger(__name__)
config = load_config()

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
                logging.warning(f'Failed to delete {file_path}: {str(e)}')
    except Exception as e:
        logging.error(f'Error cleaning data directory: {str(e)}')

def main() -> dict:
    """Основная функция обработки документов"""
    config = load_config()
    output_dir = config['paths']['output_dir']
    data_dir = config['paths']['data_dir']
    
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Параллельная обработка файлов
        all_chunks = parallel_process(config)
        if not all_chunks:
            logging.error("No files were processed")
            return {"error": "No files processed"}

        # Инициализация процессора файлов
        processor = FileProcessor(config)
        processed_files = []
        
        # Сохранение результатов
        for file_path, chunks in tqdm(all_chunks.items(), desc="Сохранение чанков"):
            if not chunks:
                continue
                
            output_file = os.path.join(
                output_dir, 
                f"{os.path.splitext(os.path.basename(file_path))[0]}.json"
            )
            processor.save_chunks(chunks, output_file)
            processed_files.append(file_path)
            logging.info(f"Processed {file_path} -> {len(chunks)} chunks")
        
        # Создание глобального индекса
        processor.create_global_index(output_dir)
        
        # Очистка каталога data после успешной обработки
        clear_data_directory(data_dir)
        
        result = {
            "processed_files": processed_files,
            "total_chunks": sum(len(chunks) for chunks in all_chunks.values())
        }
        logging.info(f"Processing complete: {result}")
        return result
        
    except Exception as e:
        logging.error(f"Processing failed: {str(e)}", exc_info=True)
        return {"error": str(e)}

async def process_uploaded_files():
    """Фоновая обработка загруженных файлов"""
    try:
        processor = FileProcessor(config)
        data_dir = config['paths']['data_dir']
        output_dir = config['paths']['output_dir']
        
        while True:
            files = [f for f in os.listdir(data_dir) 
                   if f.endswith(('.pdf', '.doc', '.docx'))]
            
            if not files:
                await asyncio.sleep(5)  # Проверяем каждые 5 секунд
                continue
            
            for file in files:
                file_path = os.path.join(data_dir, file)
                try:
                    logger.info(f"Начата обработка: {file}")
                    chunks = processor.process_file(file_path)
                    
                    output_file = os.path.join(
                        output_dir, 
                        f"{os.path.splitext(file)[0]}.json"
                    )
                    processor.save_chunks(chunks, output_file)
                    os.remove(file_path)  # Удаляем обработанный файл
                    logger.info(f"Файл обработан: {file}")
                    
                except Exception as e:
                    logger.error(f"Ошибка обработки {file}: {str(e)}")
            
            # Загрузка в Qdrant
            loaded = ingest_main()
            logger.info(f"Загружено в Qdrant: {loaded} чанков")
            
    except Exception as e:
        logger.critical(f"Фоновая обработка прервана: {str(e)}")




if __name__ == "__main__":
    result = main()
    if result.get("error"):
        print(f"Error: {result['error']}")
    else:
        print(f"Successfully processed {len(result['processed_files'])} files")