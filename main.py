# main.py
import os
import asyncio
import shutil
import uuid
from fastapi import FastAPI, Request, HTTPException, Form, UploadFile, File, Body
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointIdsList, Filter, FieldCondition, MatchValue
from utils.helpers import load_config, generate_unique_id
from datetime import datetime
import pandas as pd
from collections import defaultdict
from typing import Dict, List, Optional, Annotated
from sentence_transformers import SentenceTransformer
from pathlib import Path
import logging
from llm_client import llm_client
from fastapi.responses import HTMLResponse

app = FastAPI()
config = load_config()

# Настройка шаблонов и статических файлов
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# Инициализация клиентов
qdrant_client = QdrantClient(
    host=config['qdrant']['host'],
    port=config['qdrant']['port'],
    timeout=10
)
embedding_model = SentenceTransformer(config['processing']['embedding_model'])




@app.on_event("startup")
async def startup_event():
    try:
        qdrant_client.get_collection(config['qdrant']['collection_name'])
    except Exception:
        qdrant_client.recreate_collection(
            collection_name=config['qdrant']['collection_name'],
            vectors_config=VectorParams(
                size=config['qdrant']['vector_size'],
                distance=Distance.COSINE
            )
        )

# Загрузка файлов
@app.post("/upload")
async def upload_files(files: Annotated[List[UploadFile], File(...)]):
    try:
        saved_files = []
        data_dir = config['paths']['data_dir']
        
        for file in files:
            # Генерируем уникальное имя файла
            file_ext = Path(file.filename).suffix
            new_filename = f"{generate_unique_id()}{file_ext}"
            file_path = os.path.join(data_dir, new_filename)
            
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            saved_files.append(new_filename)
        
        # Запускаем обработку в фоне
        asyncio.create_task(process_and_ingest_files())
        
        return JSONResponse(
            status_code=200,
            content={"message": f"Файлы успешно загружены: {', '.join(saved_files)}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {str(e)}")

async def process_and_ingest_files() -> Dict:
    """Запуск обработки документов"""
    from process import main as process_main
    from ingest import main as ingest_main
    
    try:
        # Обработка документов
        process_result = process_main()
        if not process_result:
            raise ValueError("No files were processed")
        
        # Загрузка в Qdrant
        loaded_chunks = ingest_main()
        
        return {
            "processed_files": len(process_result["processed_files"]),
            "loaded_chunks": loaded_chunks
        }
    except Exception as e:
        logging.error(f"Ошибка обработки документов: {str(e)}")
        return {
            "error": str(e),
            "processed_files": 0,
            "loaded_chunks": 0
        }

# Удаление документов (обновленная версия)
@app.post("/documents/delete")
async def delete_document(request: Request, file_id: str = Form(...)):
    try:
        # Фильтр для поиска точек по file_id
        filter_ = Filter(
            must=[
                FieldCondition(
                    key="metadata.file_id",
                    match=MatchValue(value=file_id)
                )
            ]
        )
        
        # Находим все точки для удаления
        points = []
        next_offset = None
        while True:
            records, next_offset = qdrant_client.scroll(
                collection_name=config['qdrant']['collection_name'],
                scroll_filter=filter_,
                limit=100,
                offset=next_offset,
                with_payload=False
            )
            if not records:
                break
            points.extend([record.id for record in records])
            if next_offset is None:
                break
        
        if points:
            qdrant_client.delete(
                collection_name=config['qdrant']['collection_name'],
                points_selector=PointIdsList(points=points)
            )
        
        # Удаляем файл из data_dir
        data_dir = config['paths']['data_dir']
        for filename in os.listdir(data_dir):
            if file_id in filename:
                os.remove(os.path.join(data_dir, filename))
                break
        
        return RedirectResponse("/documents", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": f"Ошибка удаления документа: {str(e)}"
            },
            status_code=500
        )

# Очистка всей базы данных
@app.post("/purge")
async def purge_database():
    try:
        # Удаляем коллекцию
        qdrant_client.delete_collection(config['qdrant']['collection_name'])
        
        # Пересоздаем пустую коллекцию
        qdrant_client.recreate_collection(
            collection_name=config['qdrant']['collection_name'],
            vectors_config=VectorParams(
                size=config['qdrant']['vector_size'],
                distance=Distance.COSINE
            )
        )
        
        # Очищаем директории
        data_dir = config['paths']['data_dir']
        processed_dir = config['paths']['output_dir']
        
        for dir_path in [data_dir, processed_dir]:
            for filename in os.listdir(dir_path):
                file_path = os.path.join(dir_path, filename)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
        
        return JSONResponse(
            status_code=200,
            content={"message": "База данных успешно очищена"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def get_collection_info() -> Dict:
    """Получение информации о коллекции"""
    collection = qdrant_client.get_collection(config['qdrant']['collection_name'])
    count = qdrant_client.count(config['qdrant']['collection_name'])
    return {
        "name": config['qdrant']['collection_name'],
        "status": collection.status,
        "vectors_count": collection.vectors_count,
        "points_count": count.count
    }

async def get_detailed_stats() -> Dict:
    """Получение детальной статистики по документам"""
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

async def process_documents() -> Dict:
    """Запуск обработки документов"""
    from process import main as process_main
    from ingest import main as ingest_main
    
    processed_files = process_main()
    loaded_chunks = ingest_main()
    
    return {
        "processed_files": processed_files,
        "loaded_chunks": loaded_chunks
    }


@app.get("/")
async def dashboard(request: Request):
    try:
        collection_info = await get_collection_info()
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
                "time_stats": stats['time_stats'],
                "total_chunks": collection_info['points_count'],
                "has_llm": True  # Добавляем флаг наличия LLM
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

@app.get("/documents")
async def documents_page(request: Request):
    """Страница управления документами"""
    try:
        stats = await get_detailed_stats()
        return templates.TemplateResponse(
            "documents.html",
            {
                "request": request,
                "documents": stats['documents']
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": f"Ошибка получения документов: {str(e)}"
            },
            status_code=500
        )

@app.get("/search")
async def search_page(request: Request):
    """Страница поиска"""
    return templates.TemplateResponse("search.html", {"request": request})

@app.post("/search")
async def perform_search(request: Request, query: str = Form(...)):
    """Выполнение поиска"""
    try:
        # Векторизация запроса
        query_embedding = embedding_model.encode(query)
        
        # Поиск в Qdrant
        results = qdrant_client.search(
            collection_name=config['qdrant']['collection_name'],
            query_vector=query_embedding,
            limit=5,
            with_payload=True
        )
        
        # Форматирование результатов
        formatted_results = []
        for hit in results:
            payload = hit.payload
            metadata = payload.get('metadata', {})
            formatted_results.append({
                "score": hit.score,
                "text": payload.get('text', ''),
                "source": metadata.get('source', 'Неизвестно'),
                "page": metadata.get('page', 'N/A')
            })
        
        return templates.TemplateResponse(
            "search_results.html",
            {
                "request": request,
                "query": query,
                "results": formatted_results
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": f"Ошибка поиска: {str(e)}"
            },
            status_code=500
        )

@app.post("/reprocess")
async def reprocess_documents():
    """Переобработка документов"""
    try:
        result = await process_documents()
        return {
            "status": "success",
            "message": "Документы успешно переобработаны",
            "details": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик ошибок"""
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "error": f"Произошла ошибка: {str(exc)}"
        },
        status_code=500
    )

# Добавим новый endpoint для чата

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.post("/api/chat")
async def chat_with_document(data: Dict = Body(...)):
    question = data.get('question', '')
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    try:
        # 1. Векторизация вопроса
        query_embedding = embedding_model.encode(question).tolist()
        print(f"Вектор вопроса: {query_embedding[:5]}...")  # Логируем первые 5 значений

        # 2. Поиск в Qdrant с базовыми параметрами
        results = qdrant_client.search(
            collection_name=config['qdrant']['collection_name'],
            query_vector=query_embedding,
            limit=3,  # Берем 3 наиболее релевантных результата
            with_payload=True,
            score_threshold=0.5  # Минимальный порог схожести
        )
        
        print(f"Найдено результатов: {len(results)}")  # Отладочная информация

        # 3. Формирование контекста с проверкой
        context = ""
        if results:
            context_parts = []
            for hit in results:
                payload = hit.payload
                if payload and 'text' in payload and 'metadata' in payload:
                    source = payload['metadata'].get('source', 'Неизвестный источник')
                    page = payload['metadata'].get('page', 'N/A')
                    context_parts.append(
                        f"Источник: {source}\n"
                        f"Страница: {page}\n"
                        f"Текст: {payload['text']}\n"
                        f"Сходство: {hit.score:.2f}\n"
                        "———"
                    )
            context = "\n".join(context_parts)
        
        print(f"Сформированный контекст:\n{context}")  # Логируем контекст

        # 4. Формирование промта
        prompt = (
            f"{config['llm']['system_prompt']}\n\n"
            f"Контекст:\n{context if context else 'Нет релевантного контекста'}\n\n"
            f"Вопрос: {question}\n\n"
            "Ответ:"
        )

        # 5. Генерация ответа
        response = await llm_client.generate_response(
            prompt=prompt,
            **config['llm']['generation_params']
        )
        
        return {
            "response": response,
            "context_used": bool(context),
            "sources": [hit.payload.get('metadata', {}) for hit in results] if results else []
        }
        
    except Exception as e:
        logging.error(f"Ошибка в chat_with_document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def format_context(search_results) -> str:
    """Форматирует результаты поиска в читаемый контекст для LLM"""
    context_parts = []
    max_context_length = config['llm']['context_window'] // 2  # Оставляем место для ответа
    
    for hit in sorted(search_results, key=lambda x: -x.score)[:3]:  # Берем топ-3 результата
        payload = hit.payload
        metadata = payload.get('metadata', {})
        
        # Форматируем каждый фрагмент контекста
        context_part = (
            f"### Документ: {metadata.get('source', 'Без названия')}\n"
            f"### Раздел: {metadata.get('chapter', 'Нет информации')}\n"
            f"### Страница: {metadata.get('page', 'N/A')}\n"
            f"Контент:\n{payload.get('text', '')}\n\n"
        )
        
        # Проверяем, не превысим ли максимальную длину
        if len('\n'.join(context_parts) + context_part) < max_context_length:
            context_parts.append(context_part)
        else:
            break
    
    return '\n'.join(context_parts)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)