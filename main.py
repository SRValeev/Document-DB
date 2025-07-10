import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from utils.helpers import load_config, clear_directory
import logging
import os

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stdout.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Управление жизненным циклом приложения"""
    config = load_config()
    
    # Инициализация Qdrant
    qdrant_client = QdrantClient(
        host=config['qdrant']['host'],
        port=config['qdrant']['port'],
        timeout=10
    )
    app.state.qdrant_client = qdrant_client
    
    # Инициализация модели эмбеддингов
    from sentence_transformers import SentenceTransformer
    app.state.embedding_model = SentenceTransformer(
        config['processing']['embedding_model']
    )
    
    # Очистка директорий при старте
    clear_directory(config['paths']['data_dir'])
    clear_directory(config['paths']['output_dir'], exclude=["global_index.json"])
    
    # Создание коллекции (если не существует)
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
    
    logger.info("Сервис запущен, инициализация завершена")
    
    # Запуск фоновой задачи обработки
    async def process_files_background():
        from process import process_uploaded_files
        await process_uploaded_files()
    
    asyncio.create_task(process_files_background())
    
    from utils.context_builder import ContextBuilder
    app.state.context_builder = ContextBuilder(config)

    yield  # Здесь работает приложение
    
    # Очистка при завершении
    clear_directory(config['paths']['data_dir'])
    logger.info("Сервис остановлен, директории очищены")

# Создание FastAPI приложения
app = FastAPI(
    title="RAG Document Assistant",
    lifespan=lifespan
)

# Подключение статических файлов
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# Подключение роутеров
from routes import router
app.include_router(router)

# Корневой эндпоинт для проверки
@app.get("/")
async def root():
    return {
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "dashboard": "/",
            "documents": "/documents",
            "upload": "/upload",
            "search": "/search",
            "chat": "/chat"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)