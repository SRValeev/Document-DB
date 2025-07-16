import os
import json
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from utils.helpers import load_config, setup_logging
from utils.helpers import clear_directory
import logging
import numpy as np

def main() -> int:
    """Основная функция загрузки данных в Qdrant"""
    config = load_config()
    setup_logging(config['paths']['log_file'])
    processed_dir = config['paths']['output_dir']
    perf_config = config.get('performance', {})
    
    try:
        client = QdrantClient(
            host=config['qdrant']['host'],
            port=config['qdrant']['port']
        )
        
        # Создаем коллекцию (если не существует)
        try:
            client.get_collection(config['qdrant']['collection_name'])
            logging.info("Collection already exists")
        except Exception as e:
            logging.warning(f"Collection not found, creating new: {str(e)}")
            client.recreate_collection(
                collection_name=config['qdrant']['collection_name'],
                vectors_config=VectorParams(
                    size=config['qdrant']['vector_size'],
                    distance=Distance.COSINE
                )
            )
            logging.info("Collection created successfully")
        
        points = []
        processed_files = 0
        
        for file in os.listdir(processed_dir):
            if file.endswith('.json') and file != 'global_index.json':
                file_path = os.path.join(processed_dir, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    chunks = json.load(f)
                    for chunk in chunks:
                        if 'embedding' in chunk and chunk['embedding'] is not None:
                            # Проверка на NaN
                            if not any(np.isnan(x) for x in chunk['embedding']):
                                points.append(PointStruct(
                                    id=chunk['id'],
                                    vector=chunk['embedding'],
                                    payload={
                                        "text": chunk['text'],
                                        "metadata": chunk['metadata'],
                                        "vector": chunk['embedding']
                                    }
                                ))
                    processed_files += 1
        
        if not points:
            logging.warning("No data to load")
            return 0
        
        # Используем настройки производительности из конфига
        batch_size = perf_config.get('qdrant_batch_size', 20)
        success_count = 0
        
        for i in tqdm(range(0, len(points), batch_size), desc="Загрузка в Qdrant"):
            batch = points[i:i+batch_size]
            try:
                operation_result = client.upsert(
                    collection_name=config['qdrant']['collection_name'],
                    points=batch,
                    wait=True
                )
                
                if operation_result.status == 'completed':
                    success_count += len(batch)
                else:
                    logging.error(f"Batch {i//batch_size} failed: {operation_result.status}")
                    batch_size = max(1, batch_size // 2)
            except Exception as e:
                logging.error(f"Batch {i//batch_size} error: {str(e)}")
                batch_size = max(1, batch_size // 2)
        
        clear_directory(config['paths']['output_dir'])
        logging.info(f"Successfully loaded {success_count}/{len(points)} chunks from {processed_files} files")
        return success_count
    
   
        return success_count



    except Exception as e:
        logging.error(f"Critical error in ingest: {str(e)}", exc_info=True)
        return 0

if __name__ == "__main__":
    loaded_chunks = main()
    if loaded_chunks > 0:
        logging.info(f"Data loaded successfully: {loaded_chunks} chunks")
    else:
        logging.error("Failed to load data")