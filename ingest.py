import os
import json
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from utils.helpers import load_config

def main():
    config = load_config()
    processed_dir = config['paths']['output_dir']
    
    # Инициализация клиента Qdrant с обработкой ошибок
    try:
        client = QdrantClient(
            host=config['qdrant']['host'],
            port=config['qdrant']['port'],
            timeout=10  # Увеличиваем таймаут
        )
        
        # Проверка соединения
        client.get_collections()
    except Exception as e:
        print(f"Ошибка подключения к Qdrant: {str(e)}")
        print("Проверьте, запущен ли Qdrant сервер и доступен по указанному адресу")
        return
    
    # Создание коллекции
    try:
        client.recreate_collection(  # Используем recreate вместо create
            collection_name=config['qdrant']['collection_name'],
            vectors_config=VectorParams(
                size=config['qdrant']['vector_size'],
                distance=Distance.COSINE
            )
        )
        print(f"Коллекция {config['qdrant']['collection_name']} создана")
    except Exception as e:
        print(f"Ошибка создания коллекции: {str(e)}")
        return
    
    # Загрузка чанков
    points = []
    for file in os.listdir(processed_dir):
        if file.endswith('.json') and file != 'global_index.json':
            file_path = os.path.join(processed_dir, file)
            try:
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
            except Exception as e:
                print(f"Ошибка загрузки файла {file}: {str(e)}")
                continue
    
    if not points:
        print("Нет данных для загрузки")
        return
    
    # Пакетная загрузка с обработкой ошибок
    batch_size = 50  # Уменьшенный размер батча
    success_count = 0
    
    for i in tqdm(range(0, len(points), batch_size), desc="Загрузка в Qdrant"):
        batch = points[i:i+batch_size]
        try:
            client.upsert(
                collection_name=config['qdrant']['collection_name'],
                points=batch,
                wait=True  # Ждем подтверждения
            )
            success_count += len(batch)
        except Exception as e:
            print(f"\nОшибка загрузки батча {i//batch_size}: {str(e)}")
            # Можно добавить логику повторной попытки
    
    print(f"\nУспешно загружено {success_count}/{len(points)} чанков")

if __name__ == "__main__":
    main()