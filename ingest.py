import os
import json
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from utils.helpers import load_config

def main() -> int:
    """Основная функция загрузки данных в Qdrant"""
    config = load_config()
    processed_dir = config['paths']['output_dir']
    perf_config = config.get('performance', {})
    
    try:
        client = QdrantClient(
            host=config['qdrant']['host'],
            port=config['qdrant']['port'],
            timeout=30  # Увеличили таймаут
        )
        
        # Создаем коллекцию (если не существует)
        try:
            client.get_collection(config['qdrant']['collection_name'])
        except:
            client.recreate_collection(
                collection_name=config['qdrant']['collection_name'],
                vectors_config=VectorParams(
                    size=config['qdrant']['vector_size'],
                    distance=Distance.COSINE
                )
            )
        
        points = []
        for file in os.listdir(processed_dir):
            if file.endswith('.json') and file != 'global_index.json':
                file_path = os.path.join(processed_dir, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    chunks = json.load(f)
                    for chunk in chunks:
                        if 'embedding' in chunk:
                            points.append(PointStruct(
                                id=chunk['id'],
                                vector=chunk['embedding'],
                                payload={
                                    "text": chunk['text'],
                                    "metadata": chunk['metadata']
                                }
                            ))
        
        if not points:
            print("Нет данных для загрузки")
            return 0
        
        # Используем настройки производительности из конфига
        batch_size = perf_config.get('qdrant_batch_size', 50)
        success_count = 0
        
        for i in tqdm(range(0, len(points), batch_size), desc="Загрузка в Qdrant"):
            batch = points[i:i+batch_size]
            try:
                client.upsert(
                    collection_name=config['qdrant']['collection_name'],
                    points=batch,
                    wait=True,
                    timeout=60  # Увеличили таймаут
                )
                success_count += len(batch)
            except Exception as e:
                print(f"\nОшибка загрузки батча {i//batch_size}: {str(e)}")
                # Пробуем уменьшить размер батча
                batch_size = max(10, batch_size // 2)
                print(f"Уменьшаем размер батча до {batch_size}")
        
        print(f"\nУспешно загружено {success_count}/{len(points)} чанков")
        return success_count
    
    except Exception as e:
        print(f"Критическая ошибка: {str(e)}")
        return 0

if __name__ == "__main__":
    loaded_chunks = main()
    if loaded_chunks > 0:
        print("Данные успешно загружены в Qdrant")
    else:
        print("Не удалось загрузить данные")