import asyncio
from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException, Body
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, PointIdsList, VectorParams, Distance
from sentence_transformers import SentenceTransformer
from utils.helpers import load_config, normalize_text, generate_unique_id
from utils.context_builder import ContextBuilder
from utils.llm_client import llm_client
import os
import shutil
import uuid
from pathlib import Path
import logging
import json
from datetime import datetime
import pandas as pd
from collections import defaultdict
from typing import Dict, List, Optional

router = APIRouter()
config = load_config()
templates = Jinja2Templates(directory="web/templates")

# Инициализация клиентов
qdrant_client = QdrantClient(
    host=config['qdrant']['host'],
    port=config['qdrant']['port'],
    timeout=10
)
embedding_model = SentenceTransformer(config['processing']['embedding_model'])
context_builder = ContextBuilder(config)
logger = logging.getLogger(__name__)

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
            doc_stats[file_id]['chunks'] = 1
            doc_stats[file_id]['size'] = len(text)
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


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Главная страница с аналитикой"""
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
                "has_llm": True
            }
        )
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": str(e)},
            status_code=500
        )
    
def _get_file_types_stats(global_index: dict) -> dict:
    """Статистика по типам файлов"""
    from collections import defaultdict
    types = defaultdict(int)
    for file in global_index.get('files', []):
        if 'path' in file:
            ext = os.path.splitext(file['path'])[1].lower()
            types[ext] += 1
    return dict(types)

@router.get("/documents", response_class=HTMLResponse)
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
        logger.error(f"Documents page error: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": str(e)},
            status_code=500
        )

@router.post("/documents/delete")
async def delete_document(request: Request, file_id: str = Form(...)):
    """Удаление документа"""
    try:
        # Фильтр для поиска точек по file_id
        filter_ = Filter(
            must=[
                FieldCondition(
                    key="metadata.file_id",
                    match=MatchValue(value=file_id))
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
        logger.error(f"Delete document error: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": str(e)},
            status_code=500
        )

@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    """Страница поиска"""
    return templates.TemplateResponse("search.html", {"request": request})

@router.post("/search")
async def perform_search(request: Request, query: str = Form(...)):
    """Обработка поискового запроса"""
    try:
        # Векторизация запроса
        query_embedding = embedding_model.encode(query).tolist()
        
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
        logger.error(f"Search error: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": str(e)},
            status_code=500
        )

@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Страница загрузки файлов"""
    return templates.TemplateResponse("upload.html", {"request": request})

@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    try:
        saved_files = []
        data_dir = config['paths']['data_dir']
        
        for file in files:
            # Сохраняем оригинальное имя с добавлением UUID
            original_name = Path(file.filename).stem
            ext = Path(file.filename).suffix
            new_filename = f"{original_name}_{generate_unique_id()}{ext}"
            
            file_path = os.path.join(data_dir, new_filename)
            
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            saved_files.append({
                "original_name": file.filename,
                "saved_as": new_filename
            })
            logger.info(f"Uploaded file: {new_filename}")
        
        # Запускаем обработку в фоне
        from process import process_uploaded_files
        asyncio.create_task(process_uploaded_files())
        
        # Перенаправляем на страницу документов
        return RedirectResponse(url="/documents", status_code=303)
    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Чат-интерфейс"""
    return templates.TemplateResponse("chat.html", {"request": request})

@router.post("/api/chat")
async def chat_with_document(request: Request, data: Dict = Body(...)):
    try:
        config = load_config()
        question = data.get('question', '').strip()
        if not question:
            raise HTTPException(status_code=400, detail="Требуется вопрос")

        # Получаем все параметры из конфига
        qdrant_config = config['qdrant']
        processing_config = config['processing']
        context_config = config['context']
        llm_config = config['llm']

        # Векторизация вопроса
        question_embedding = request.app.state.embedding_model.encode(
            question,
            normalize_embeddings=True
        ).tolist()

        # Поиск с параметрами из конфига
        search_results = request.app.state.qdrant_client.search(
            collection_name=qdrant_config['collection_name'],
            query_vector=question_embedding,
            limit=context_config['max_chunks'] * 2,  # Берем в 2 раза больше для MMR
            with_payload=True,
            with_vectors=context_config.get('with_vectors', False),
            score_threshold=processing_config['min_similarity']
        )

        # Формирование контекста с MMR (если включено в конфиге)
        if context_config.get('mmr_enabled', True):
            context_builder = request.app.state.context_builder
            context = context_builder.build_context(
                query_embedding=question_embedding,
                qdrant_results=search_results
            )
        else:
            # Простая сортировка по релевантности
            context_chunks = []
            for hit in sorted(search_results, key=lambda x: x.score, reverse=True):
                if hit.score < processing_config['min_similarity']:
                    continue
                payload = hit.payload
                context_chunks.append(
                    f"Источник: {payload.get('metadata', {}).get('source', '')}\n"
                    f"{payload.get('text', '')}"
                )
            context = "\n\n".join(context_chunks[:context_config['max_chunks']])

        # Логирование для отладки
        logger.debug(f"Found {len(search_results)} fragments, using {min(len(search_results), context_config['max_chunks'])}")
        
        if not context.strip():
            return JSONResponse(
                content={"response": "Релевантная информация не найдена в документах"},
                status_code=404
            )

        # Генерация ответа
        llm_response = await llm_client.generate_response(
            prompt=question,
            context=context,
            **llm_config['generation_params']
        )

        return {"response": llm_response}

    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/purge")
async def purge_database():
    """Очистка всей базы данных"""
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
        logger.error(f"Purge error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/check_data")
async def debug_check_data():
    """Проверка первых 3 записей в Qdrant"""
    try:
        records = qdrant_client.scroll(
            collection_name=config['qdrant']['collection_name'],
            limit=3,
            with_payload=True
        )[0]
        
        formatted_records = []
        for record in records:
            formatted_records.append({
                "id": str(record.id),
                "payload": record.payload,
                "vector": record.vector[:5] + ["..."] if record.vector else None
            })
        
        return JSONResponse(content=formatted_records)
    except Exception as e:
        logger.error(f"Debug check error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

