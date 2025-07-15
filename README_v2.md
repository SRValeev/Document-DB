# RAG Document Assistant v2.0 🚀

**Enterprise-ready RAG (Retrieval-Augmented Generation) system** для работы с документами с современной архитектурой, безопасностью и масштабируемостью.

## 🌟 Новые возможности v2.0

### 🔐 Безопасность
- **JWT аутентификация** с refresh токенами
- **Rate limiting** и защита от брутфорса
- **Валидация данных** на всех уровнях
- **API ключи** для программного доступа
- **Админ панель** для управления пользователями

### 🏗️ Архитектура
- **Асинхронная обработка** документов
- **Микросервисная архитектура** с FastAPI
- **Структурированное логирование** и метрики
- **Docker контейнеризация**
- **Health checks** и мониторинг

### 📊 Мониторинг
- **Структурированные логи** в JSON формате
- **Метрики производительности**
- **Health check** эндпоинты
- **Интеграция с Prometheus/Grafana**

### 🚀 Производительность
- **Параллельная обработка** файлов
- **Кэширование** с Redis
- **Оптимизированные эмбеддинги**
- **Пагинация** и фильтры

## 📋 Системные требования

- Python 3.11+
- Docker & Docker Compose
- 4GB+ RAM
- 2GB+ свободного места

## 🚀 Быстрый старт

### 1. Клонирование и подготовка

```bash
# Клонируйте репозиторий
git clone <repository-url>
cd rag-document-assistant

# Создайте файл окружения
cp .env.example .env
# Отредактируйте .env согласно вашим настройкам
```

### 2. Запуск с Docker (рекомендуется)

```bash
# Запуск основных сервисов
docker-compose up -d

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f app
```

### 3. Локальная установка

```bash
# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt

# Загрузка spaCy модели
python -m spacy download ru_core_news_md

# Запуск приложения
python -m uvicorn app.main:app --reload
```

## 📚 API Документация

После запуска приложения:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
- **Метрики**: http://localhost:8000/metrics

### 🔑 Аутентификация

#### Регистрация пользователя
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user",
    "email": "user@example.com",
    "password": "password123",
    "full_name": "Test User"
  }'
```

#### Вход в систему
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user",
    "password": "password123"
  }'
```

### 📄 Работа с документами

#### Загрузка документа
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@document.pdf"
```

#### Поиск в документах
```bash
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "ваш поисковый запрос",
    "limit": 5,
    "min_relevance": 0.7
  }'
```

### 💬 Чат с документами

#### Создание чат-сессии
```bash
curl -X POST "http://localhost:8000/api/v1/chat/sessions" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Новый чат"}'
```

#### Отправка сообщения
```bash
curl -X POST "http://localhost:8000/api/v1/chat/sessions/SESSION_ID/messages" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message_content": "Расскажи о документе"}'
```

## 🔧 Конфигурация

### Основные настройки (.env)

```env
# Безопасность
SECURITY_SECRET_KEY=your-secret-key-here
SECURITY_ACCESS_TOKEN_EXPIRE_MINUTES=30

# База данных
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Обработка документов
PROCESSING_MAX_FILE_SIZE_MB=50
PROCESSING_CHUNK_SIZE=768
PROCESSING_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2

# LLM
LLM_API_URL=http://localhost:1234/v1
LLM_MODEL=google/gemma-3-4b
```

### Поддерживаемые форматы документов

- **PDF** (.pdf) - с OCR поддержкой
- **Word** (.docx, .doc)
- **Текст** (.txt)

## 🐳 Docker развертывание

### Базовый запуск
```bash
docker-compose up -d
```

### С мониторингом
```bash
docker-compose --profile monitoring up -d
```

### Продакшн с Nginx
```bash
docker-compose --profile production up -d
```

## 📊 Мониторинг и логирование

### Prometheus метрики
- Доступны на `/metrics`
- Количество запросов, время ответа
- Статистика обработки документов

### Grafana дашборды
- Панель мониторинга: http://localhost:3000
- Логин: admin / admin (по умолчанию)

### Структурированные логи
```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "level": "INFO",
  "logger": "app.api.routes",
  "message": "Document processed successfully",
  "request_id": "req_123456",
  "user_id": "user_789",
  "document_id": "doc_abc123",
  "processing_time": 2.5
}
```

## 🧪 Тестирование

```bash
# Запуск всех тестов
pytest

# С покрытием кода
pytest --cov=app

# Только юнит-тесты
pytest tests/unit/

# Интеграционные тесты
pytest tests/integration/
```

## 📁 Структура проекта

```
rag-document-assistant-v2/
├── app/                      # Основное приложение
│   ├── core/                 # Ядро системы
│   │   ├── config.py         # Конфигурация
│   │   ├── security.py       # Безопасность
│   │   ├── logging.py        # Логирование
│   │   └── exceptions.py     # Исключения
│   ├── api/                  # API роуты
│   │   ├── auth.py          # Аутентификация
│   │   └── routes.py        # Основные маршруты
│   ├── services/            # Бизнес-логика
│   │   ├── document_processor.py  # Обработка документов
│   │   └── models.py        # Модели данных
│   └── main.py              # Главный файл приложения
├── tests/                   # Тесты
├── docker-compose.yml       # Docker композиция
├── Dockerfile              # Docker образ
├── requirements.txt        # Python зависимости
└── README_v2.md           # Документация
```

## 🔒 Безопасность

### Рекомендации для продакшн

1. **Измените секретные ключи**:
   ```env
   SECURITY_SECRET_KEY=your-production-secret-key
   ```

2. **Настройте CORS**:
   ```env
   CORS_ORIGINS=["https://yourdomain.com"]
   ```

3. **Используйте HTTPS**:
   - Настройте SSL сертификаты
   - Используйте Nginx как reverse proxy

4. **Ограничьте доступ к базам данных**:
   - Закройте порты Qdrant и Redis
   - Используйте внутреннюю сеть Docker

## 🚀 Масштабирование

### Горизонтальное масштабирование
```bash
# Увеличение количества реплик приложения
docker-compose up -d --scale app=3
```

### Настройка производительности
```env
# Увеличение воркеров для обработки
PROCESSING_MAX_WORKERS=8
PROCESSING_BATCH_SIZE=64

# Настройка пула соединений
API_WORKERS=4
```

## 🛠️ Разработка

### Локальная разработка
```bash
# Активация режима разработки
export DEBUG=true

# Запуск с автоперезагрузкой
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Форматирование кода
```bash
# Форматирование
black app/
isort app/

# Линтинг
flake8 app/
```

## 📈 Roadmap

### v2.1 (Q2 2024)
- [ ] Поддержка больше форматов документов
- [ ] Улучшенный веб-интерфейс
- [ ] Batch API для массовой обработки
- [ ] Расширенная аналитика

### v2.2 (Q3 2024)
- [ ] Интеграция с внешними LLM (OpenAI, Anthropic)
- [ ] Многоязычная поддержка
- [ ] Федеративный поиск
- [ ] Роли и права доступа

## ❓ FAQ

**Q: Как изменить модель эмбеддингов?**
A: Измените `PROCESSING_EMBEDDING_MODEL` в .env файле

**Q: Поддерживается ли GPU?**
A: Да, установите `PROCESSING_DEVICE=cuda` в настройках

**Q: Как добавить новый формат документов?**
A: Расширьте `DocumentProcessor` класс в `services/document_processor.py`

## 🤝 Поддержка

- 📧 Email: support@example.com
- 💬 Чат: [Telegram](https://t.me/support)
- 🐛 Баги: [GitHub Issues](https://github.com/repo/issues)

## 📜 Лицензия

MIT License - см. [LICENSE](LICENSE) файл.

---

**RAG Document Assistant v2.0** - Современное решение для работы с документами 🚀