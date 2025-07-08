import os
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from utils.helpers import load_config
from datetime import datetime
import pandas as pd
from collections import defaultdict
from typing import Dict, List, Optional

app = FastAPI()
config = load_config()

# Настройка статических файлов и шаблонов
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# Инициализация клиента Qdrant
qdrant_client = QdrantClient(
    host=config['qdrant']['host'],
    port=config['qdrant']['port'],
    timeout=10
)

async def get_detailed_stats() -> Dict:
    """Получение детальной статистики по коллекции"""
    records, _ = qdrant_client.scroll(
        collection_name=config['qdrant']['collection_name'],
        limit=10000,
        with_payload=True
    )
    
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
            
            processing_date = metadata.get('processing_date')
            if processing_date:
                date_obj = datetime.strptime(processing_date, '%Y-%m-%d')
                if not doc_stats[file_id]['first_seen'] or date_obj < doc_stats[file_id]['first_seen']:
                    doc_stats[file_id]['first_seen'] = date_obj
                if not doc_stats[file_id]['last_seen'] or date_obj > doc_stats[file_id]['last_seen']:
                    doc_stats[file_id]['last_seen'] = date_obj
                date_data.append(date_obj)
            
            content_type = metadata.get('type', 'unknown')
            type_stats[content_type] += 1
            
            size_data.append(len(text))
    
    # Преобразование статистики документов
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

async def initialize_database():
    """Инициализация базы данных"""
    try:
        collection_info = qdrant_client.get_collection(config['qdrant']['collection_name'])
        if collection_info.points_count == 0:
            await process_documents()
    except Exception:
        qdrant_client.recreate_collection(
            collection_name=config['qdrant']['collection_name'],
            vectors_config=VectorParams(
                size=config['qdrant']['vector_size'],
                distance=Distance.COSINE
            )
        )
        await process_documents()

async def process_documents() -> Dict:
    """Обработка и загрузка документов"""
    from process import main as process_main
    from ingest import main as ingest_main
    
    processed_files = process_main()
    loaded_chunks = ingest_main()
    
    return {
        "processed_files": processed_files,
        "loaded_chunks": loaded_chunks
    }

@app.on_event("startup")
async def startup_event():
    """Запуск при старте сервера"""
    await initialize_database()

@app.get("/")
async def dashboard(request: Request):
    """Главная страница со статистикой"""
    try:
        collection_info = qdrant_client.get_collection(config['qdrant']['collection_name'])
        stats = await get_detailed_stats()
        
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "collection_info": collection_info,
                "documents": stats['documents'],
                "documents_count": len(stats['documents']),
                "type_stats": stats['type_stats'],
                "size_stats": stats['size_stats'],
                "time_stats": stats['time_stats']
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

@app.get("/stats")
async def stats_api():
    """API для получения статистики"""
    try:
        return await get_detailed_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reprocess")
async def reprocess_documents():
    """Переобработка документов"""
    try:
        result = await process_documents()
        return {
            "status": "success",
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Обработчик ошибок"""
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "error": f"Ошибка: {str(exc)}"
        },
        status_code=500
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)