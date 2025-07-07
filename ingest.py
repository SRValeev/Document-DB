import os
import json
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from utils.helpers import load_config

def main():
    config = load_config()
    processed_dir = config['paths']['output_dir']
    
    # Инициализация клиента Qdrant
    client = QdrantClient(
        host=config['qdrant']['host'],
        port=config['qdrant']['port']
    )
    
    # Создание коллекции (если не существует)
    try:
        client.create_collection(
            collection_name=config['qdrant']['collection_name'],
            vectors_config=VectorParams(
                size=config['qdrant']['vector_size'],
                distance=Distance.COSINE
            )
        )
    except:
        pass  # Коллекция уже существует
    
    # Загрузка всех обработанных файлов
    points = []
    chunk_id = 1
    for file in os.listdir(processed_dir):
        if file.endswith('.json') and file != 'global_index.json':
            file_path = os.path.join(processed_dir, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
                for chunk in chunks:
                    if 'embedding' in chunk:
                        points.append(PointStruct(
                            id=chunk_id,
                            vector=chunk['embedding'],
                            payload={
                                "text": chunk['text'],
                                "metadata": chunk['metadata']
                            }
                        ))
                        chunk_id += 1
    
    # Пакетная загрузка в Qdrant
    batch_size = 100
    for i in tqdm(range(0, len(points), batch_size), desc="Загрузка в Qdrant"):
        batch = points[i:i+batch_size]
        client.upsert(
            collection_name=config['qdrant']['collection_name'],
            points=batch
        )
    
    print(f"\nЗагружено {len(points)} чанков в коллекцию {config['qdrant']['collection_name']}")

if __name__ == "__main__":
    main()