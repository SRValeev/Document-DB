import os
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from utils.helpers import load_config
from datetime import datetime
import pandas as pd
from collections import defaultdict
from typing import Dict, List

app = FastAPI()
config = load_config()

# Настройка шаблонов и статических файлов
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# Инициализация клиента Qdrant
qdrant_client = QdrantClient(
    host=config['qdrant']['host'],
    port=config['qdrant']['port'],
    timeout=10
)

async def get_collection_stats() -> Dict:
    """Получение базовой статистики коллекции"""
    collection_info = qdrant_client.get_collection(config['qdrant']['collection_name'])
    return {
        "name": config['qdrant']['collection_name'],
        "status": collection_info.status,
        "vectors_count": collection_info.vectors_count,
        "points_count": qdrant_client.count(config['qdrant']['collection_name']).count
    }

async def get_detailed_stats() -> Dict:
    """Получение детальной статистики по документам"""
    try:
        # Получаем общее количество точек
        count_info = qdrant_client.count(config['qdrant']['collection_name'])
        
        if count_info.count == 0:
            return {
                'documents': [],
                'type_stats': {},
                'size_stats': {},
                'time_stats': {}
            }

        # Постраничная загрузка данных
        records = []
        next_offset = None
        batch_size = 1000
        
        while True:
            batch, next_offset = qdrant_client.scroll(
                collection_name=config['qdrant']['collection_name'],
                limit=batch_size,
                offset=next_offset,
                with_payload=True,
                with_vectors=False
            )
            records.extend(batch)
            if not next_offset:
                break

        # Анализ данных
        doc_stats = defaultdict(lambda: {
            'name': '',
            'chunks': 0,
            'size': 0,
            'types': set(),
            'pages': set(),
            'first_seen': None,
            'last_seen': None
        })
        
        type_stats = defaultdict(int)
        size_data = []
        date_data = []
        
        for record in records:
            payload = record.payload
            metadata = payload.get('metadata', {})
            file_id = metadata.get('file_id')
            text = payload.get('text', '')
            
            if file_id:
                doc_stats[file_id]['name'] = metadata.get('source', file_id)
                doc_stats[file_id]['chunks'] += 1
                doc_stats[file_id]['size'] += len(text)
                doc_stats[file_id]['types'].add(metadata.get('type', 'unknown'))
                doc_stats[file_id]['pages'].add(metadata.get('page', 0))
                
                if 'processing_date' in metadata:
                    try:
                        date_obj = datetime.strptime(metadata['processing_date'], '%Y-%m-%d')
                        if not doc_stats[file_id]['first_seen'] or date_obj < doc_stats[file_id]['first_seen']:
                            doc_stats[file_id]['first_seen'] = date_obj
                        if not doc_stats[file_id]['last_seen'] or date_obj > doc_stats[file_id]['last_seen']:
                            doc_stats[file_id]['last_seen'] = date_obj
                        date_data.append(date_obj)
                    except ValueError:
                        pass
                
                content_type = metadata.get('type', 'unknown')
                type_stats[content_type] += 1
                size_data.append(len(text))
        
        # Форматирование результатов
        documents = []
        for file_id, stats in doc_stats.items():
            documents.append({
                'id': file_id,
                'name': stats['name'],
                'chunks': stats['chunks'],
                'size_kb': stats['size'] / 1024,
                'types': list(stats['types']),
                'pages': len(stats['pages']),
                'first_seen': stats['first_seen'].strftime('%Y-%m-%d') if stats['first_seen'] else 'N/A',
                'last_seen': stats['last_seen'].strftime('%Y-%m-%d') if stats['last_seen'] else 'N/A'
            })
        
        # Анализ размеров
        size_stats = {}
        if size_data:
            size_series = pd.Series(size_data)
            size_stats = {
                'total': len(size_data),
                'avg': int(size_series.mean()),
                'min': int(size_series.min()),
                'max': int(size_series.max()),
                'percentiles': {
                    '25': int(size_series.quantile(0.25)),
                    '50': int(size_series.quantile(0.5)),
                    '75': int(size_series.quantile(0.75)),
                    '95': int(size_series.quantile(0.95))
                }
            }
        
        # Временная статистика
        time_stats = {}
        if date_data:
            date_series = pd.Series(date_data)
            time_stats = {
                'first': date_series.min().strftime('%Y-%m-%d'),
                'last': date_series.max().strftime('%Y-%m-%d'),
                'days_span': (date_series.max() - date_series.min()).days,
                'frequency': len(date_data) / ((date_series.max() - date_series.min()).days or 1)
            }
        
        return {
            'documents': documents,
            'type_stats': dict(type_stats),
            'size_stats': size_stats,
            'time_stats': time_stats
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения статистики: {str(e)}"
        )

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    try:
        # Проверяем существование коллекции
        qdrant_client.get_collection(config['qdrant']['collection_name'])
    except Exception:
        # Создаем коллекцию если не существует
        qdrant_client.recreate_collection(
            collection_name=config['qdrant']['collection_name'],
            vectors_config=VectorParams(
                size=config['qdrant']['vector_size'],
                distance=Distance.COSINE
            )
        )

@app.get("/")
async def dashboard(request: Request):
    """Главная страница со статистикой"""
    try:
        collection_stats = await get_collection_stats()
        detailed_stats = await get_detailed_stats()
        
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "collection_info": collection_stats,
                "documents": detailed_stats['documents'],
                "documents_count": len(detailed_stats['documents']),
                "type_stats": detailed_stats['type_stats'],
                "size_stats": detailed_stats['size_stats'],
                "time_stats": detailed_stats['time_stats'],
                "total_chunks": collection_stats['points_count']
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": f"Ошибка получения данных: {str(e)}"
            },
            status_code=500
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)