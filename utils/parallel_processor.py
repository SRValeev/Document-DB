import os
import json
import logging
import concurrent.futures
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from tqdm import tqdm
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

from utils.file_processor import FileProcessor
from utils.helpers import load_config

logger = logging.getLogger(__name__)
config = load_config()

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
def process_single_file(args: Tuple[Dict, str]) -> Tuple[str, List[Dict]]:
    """Обработка одного файла с повторными попытками при ошибках."""
    config, file_path = args
    try:
        processor = FileProcessor(config)
        chunks = processor.process_file(file_path)
        return (file_path, chunks)
    except Exception as e:
        logger.error(f"Error processing {file_path}: {str(e)}", exc_info=True)
        raise  # Повторная попытка будет обработана tenacity

async def parallel_process(config: Dict) -> Dict[str, List[Dict]]:
    """Асинхронная параллельная обработка файлов."""
    processor = FileProcessor(config)
    data_dir = config['paths']['data_dir']
    output_dir = config['paths']['output_dir']
    
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)

    # Сбор поддерживаемых файлов
    file_paths = []
    supported_formats = tuple(config['processing']['supported_formats'])
    
    for root, _, files in os.walk(data_dir):
        for file in files:
            if file.lower().endswith(supported_formats):
                file_paths.append(os.path.join(root, file))

    if not file_paths:
        logger.warning(f"No supported files found in {data_dir}")
        return {}

    results = {}
    num_workers = min(
        config['processing'].get('num_workers', 4),
        os.cpu_count() or 4
    )

    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
            tasks = [(config, fp) for fp in file_paths]
            
            with tqdm(total=len(tasks), desc="Processing files") as pbar:
                futures = {
                    executor.submit(process_single_file, task): task
                    for task in tasks
                }
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        file_path, chunks = future.result()
                        results[file_path] = chunks
                        logger.debug(f"Processed {file_path} -> {len(chunks)} chunks")
                    except Exception as e:
                        logger.error(f"Failed to process file: {str(e)}")
                    finally:
                        pbar.update(1)

        # Сохранение информации об обработке
        processing_info = {
            "files_processed": len(results),
            "total_chunks": sum(len(chunks) for chunks in results.values()),
            "timestamp": datetime.now().isoformat(),
            "success": True
        }
        
        info_path = Path(config['paths']['output_dir']) / "processing_info.json"
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(processing_info, f, indent=2)

        return results

    except Exception as e:
        logger.critical(f"Parallel processing failed: {str(e)}", exc_info=True)
        return {}

async def background_processing(config: Dict) -> None:
    """Фоновая обработка новых файлов."""
    while True:
        try:
            await parallel_process(config)
            await asyncio.sleep(config.get('processing_interval', 30))
        except Exception as e:
            logger.error(f"Background processing error: {str(e)}")
            await asyncio.sleep(60)