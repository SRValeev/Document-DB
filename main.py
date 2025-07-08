# Импорт необходимых библиотек
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from pathlib import Path
import uvicorn
from typing import List
import json
import os
from qdrant_client import QdrantClient
from qdrant_client.models import PointIdsList, Filter
from sentence_transformers import SentenceTransformer
from utils.helpers import load_config, normalize_text
from datetime import datetime
import pandas as pd
from collections import defaultdict

# Создание экземпляра FastAPI приложения
app = FastAPI()

# Загрузка конфигурации из файла
config = load_config()

# Настройка статических файлов и шаблонов
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# Инициализация клиента Qdrant
qdrant_client = QdrantClient(
    host=config['qdrant']['host'],
    port=config['qdrant']['port']
)

# Инициализация модели для эмбеддингов
embedding_model = SentenceTransformer(config['processing']['embedding_model'])

@app.get("/")
async def dashboard(request: Request):
    """Главная страница с информацией о состоянии системы"""
    try:
        # Получаем информацию о коллекции из Qdrant
        collection_info = qdrant_client.get_collection(config['qdrant']['collection_name'])
        
        # Получаем все точки для анализа
        records, _ = qdrant_client.scroll(
            collection_name=config['qdrant']['collection_name'],
            limit=10000,
            with_payload=True
        )
        
        # Анализ данных
        doc_stats = {}
        type_stats = {}
        size_distribution = []
        dates = []
        
        for record in records:
            metadata = record.payload.get('metadata', {})
            file_id = metadata.get('file_id')
            text = record.payload.get('text', '')
            
            # Статистика по документам
            if file_id:
                if file_id not in doc_stats:
                    doc_stats[file_id] = {
                        'name': metadata.get('source', file_id),
                        'chunks': 0,
                        'size': 0,
                        'types': set(),
                        'last_updated': metadata.get('processing_date', '')
                    }
                doc_stats[file_id]['chunks'] += 1
                doc_stats[file_id]['size'] += len(text)
                if 'type' in metadata:
                    doc_stats[file_id]['types'].add(metadata['type'])
            
            # Статистика по типам контента
            content_type = metadata.get('type', 'unknown')
            type_stats[content_type] = type_stats.get(content_type, 0) + 1
            
            # Для распределения размеров
            size_distribution.append(len(text))
            
            # Для временного анализа
            if 'processing_date' in metadata:
                dates.append(datetime.strptime(metadata['processing_date'], '%Y-%m-%d'))
        
        # Анализ временных данных
        time_analysis = {}
        if dates:
            date_series = pd.Series(dates)
            time_analysis = {
                'first_upload': date_series.min().strftime('%Y-%m-%d'),
                'last_upload': date_series.max().strftime('%Y-%m-%d'),
                'upload_frequency': (date_series.max() - date_series.min()).days / len(date_series) if len(date_series) > 1 else 0
            }
        
        # Анализ распределения размеров
        size_analysis = {}
        if size_distribution:
            size_series = pd.Series(size_distribution)
            size_analysis = {
                'avg_size': int(size_series.mean()),
                'min_size': int(size_series.min()),
                'max_size': int(size_series.max()),
                'percentiles': {
                    '25': int(size_series.quantile(0.25)),
                    '50': int(size_series.quantile(0.5)),
                    '75': int(size_series.quantile(0.75))
                }
            }
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "collection_info": collection_info,
            "documents": list(doc_stats.values()),
            "documents_count": len(doc_stats),
            "total_chunks": collection_info.points_count,
            "type_stats": type_stats,
            "time_analysis": time_analysis,
            "size_analysis": size_analysis,
            "size_distribution": size_distribution[:1000]  # Для графика
        })
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": f"Ошибка получения данных: {str(e)}"
        })

@app.get("/stats")
async def get_detailed_stats(request: Request):
    """Страница с детальной статистикой"""
    try:
        # Получаем все точки из коллекции
        records, _ = qdrant_client.scroll(
            collection_name=config['qdrant']['collection_name'],
            limit=10000,
            with_payload=True
        )
        
        if not records:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "В коллекции нет данных"
            })
        
        # Подготовка структур данных для статистики
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
        
        # Обработка всех записей
        for record in records:
            payload = record.payload
            metadata = payload.get('metadata', {})
            file_id = metadata.get('file_id')
            text = payload.get('text', '')
            
            if file_id:
                # Статистика по документам
                doc_stats[file_id]['name'] = metadata.get('source', file_id)
                doc_stats[file_id]['chunks'] += 1
                doc_stats[file_id]['size'] += len(text)
                doc_stats[file_id]['types'].add(metadata.get('type', 'unknown'))
                doc_stats[file_id]['pages'].add(metadata.get('page', 0))
                
                # Отслеживание дат
                processing_date = metadata.get('processing_date')
                if processing_date:
                    date_obj = datetime.strptime(processing_date, '%Y-%m-%d')
                    if not doc_stats[file_id]['first_seen'] or date_obj < doc_stats[file_id]['first_seen']:
                        doc_stats[file_id]['first_seen'] = date_obj
                    if not doc_stats[file_id]['last_seen'] or date_obj > doc_stats[file_id]['last_seen']:
                        doc_stats[file_id]['last_seen'] = date_obj
                    date_data.append(date_obj)
                
                # Статистика по типам контента
                content_type = metadata.get('type', 'unknown')
                type_stats[content_type] += 1
                
                # Статистика по размерам
                size_data.append(len(text))
        
        # Преобразование статистики документов в список
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
        
        # Расчет статистики по размерам
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
            },
            'histogram': _create_size_histogram(size_data)
        }
        
        # Расчет временной статистики
        time_stats = {}
        if date_data:
            date_series = pd.Series(date_data)
            time_stats = {
                'first': date_series.min().strftime('%Y-%m-%d'),
                'last': date_series.max().strftime('%Y-%m-%d'),
                'days_span': (date_series.max() - date_series.min()).days,
                'frequency': len(date_data) / ((date_series.max() - date_series.min()).days or 1)
            }
        
        return templates.TemplateResponse("stats.html", {
            "request": request,
            "documents": documents,
            "type_stats": dict(type_stats),
            "size_stats": size_stats,
            "time_stats": time_stats
        })
        
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": f"Ошибка получения статистики: {str(e)}"
        })

def _create_size_histogram(sizes):
    """Создание данных гистограммы для распределения размеров"""
    bins = [0, 50, 100, 200, 300, 400, 500, 750, 1000, 1500, 2000, float('inf')]
    labels = ['0-50', '51-100', '101-200', '201-300', '301-400', 
              '401-500', '501-750', '751-1000', '1001-1500', '1501-2000', '2000+']
    
    hist = [0] * (len(bins) - 1)
    for size in sizes:
        for i in range(len(bins) - 1):
            if bins[i] <= size < bins[i+1]:
                hist[i] += 1
                break
    
    return {
        'labels': labels,
        'data': hist
    }

@app.get("/search")
async def search_page(request: Request):
    """Страница поиска"""
    return templates.TemplateResponse("search.html", {"request": request})

@app.post("/search")
async def perform_search(request: Request, query: str = Form(...)):
    """Выполнение поиска по базе"""
    try:
        # Векторизация запроса
        query_embedding = embedding_model.encode([normalize_text(query)])[0].tolist()
        
        # Поиск в Qdrant
        results = qdrant_client.search(
            collection_name=config['qdrant']['collection_name'],
            query_vector=query_embedding,
            limit=5,
            with_payload=True
        )
        
        # Форматирование результатов
        formatted_results = []
        for idx, hit in enumerate(results, 1):
            payload = hit.payload
            metadata = payload.get('metadata', {})
            formatted_results.append({
                "id": idx,
                "source": metadata.get('source', 'Неизвестно'),
                "page": metadata.get('page', 'N/A'),
                "score": f"{hit.score:.2f}",
                "text": payload.get('text', '')
            })
        
        return templates.TemplateResponse("search_results.html", {
            "request": request,
            "query": query,
            "results": formatted_results
        })
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": f"Ошибка поиска: {str(e)}"
        })

@app.get("/documents")
async def documents_list(request: Request):
    """Страница управления документами"""
    try:
        # Получаем список всех документов
        records, _ = qdrant_client.scroll(
            collection_name=config['qdrant']['collection_name'],
            limit=10000,
            with_payload=True
        )
        
        doc_stats = {}
        for record in records:
            metadata = record.payload.get('metadata', {})
            file_id = metadata.get('file_id')
            if file_id:
                if file_id not in doc_stats:
                    doc_stats[file_id] = {
                        'id': file_id,
                        'name': metadata.get('source', file_id),
                        'chunks': 0
                    }
                doc_stats[file_id]['chunks'] += 1
        
        return templates.TemplateResponse("documents.html", {
            "request": request,
            "documents": list(doc_stats.values())
        })
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": f"Ошибка получения документов: {str(e)}"
        })

@app.post("/documents/delete")
async def delete_document(request: Request, file_id: str = Form(...)):
    """Удаление документа из коллекции"""
    try:
        # Находим все точки документа
        records, _ = qdrant_client.scroll(
            collection_name=config['qdrant']['collection_name'],
            limit=10000,
            with_payload=True
        )
        
        points_to_delete = []
        for record in records:
            metadata = record.payload.get('metadata', {})
            if metadata.get('file_id') == file_id:
                points_to_delete.append(record.id)
        
        # Удаляем точки батчами
        if points_to_delete:
            qdrant_client.delete(
                collection_name=config['qdrant']['collection_name'],
                points_selector=PointIdsList(points=points_to_delete)
            )
        
        return RedirectResponse("/documents", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": f"Ошибка удаления документа: {str(e)}"
        })

@app.post("/documents/upload")
async def upload_document(request: Request, files: List[UploadFile] = File(...)):
    """Загрузка новых документов"""
    try:
        # Создаем временную директорию
        temp_dir = config['paths']['tempdir']
        os.makedirs(temp_dir, exist_ok=True)
        
        # Сохраняем файлы
        saved_files = []
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as buffer:
                buffer.write(await file.read())
            saved_files.append(file_path)
        
        # Запускаем обработку (в реальной системе лучше через Celery)
        from process import main
        main()
        
        return RedirectResponse("/documents", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": f"Ошибка загрузки документа: {str(e)}"
        })

if __name__ == "__main__":
    # Запуск сервера Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)