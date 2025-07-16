# RAG Document Assistant v2.0 🚀
## Перед запуском
**Скачать и установить**
- https://github.com/qdrant/qdrant/releases
- https://www.ghostscript.com/releases/gpdldnld.html
- Создать виртуальное окружение python -m venv "%ИМЯ СЕСТРА, ИМЯ!%"
- Активировать виртуальное окружение.
**Установить зависимости, для запуска на минималках желательно использовать u_core_news_md и sentence-transformers/paraphrase-multilingual-mpnet-base-v2**
- pip install --upgrade pip
- pip install -r requirements\requirements.txt
- python -m spacy download ru_core_news_md

## Linux Deployment
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
SPACY_MODEL="ru_core_news_lg" python -m spacy download $SPACY_MODEL
```


**Большие модели**
- https://github.com/explosion/spacy-models/releases/download/ru_core_news_lg-3.7.0/ru_core_news_lg-3.7.0-py3-none-any.whl
- python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('intfloat/multilingual-e5-large'); model.save(r'%DIST_DIR%\\models\\multilingual-e5-large')"
- или https://huggingface.co/intfloat/multilingual-e5-large

## Особенности конфигурации для больших моделей
- В config.yaml укажите:
```yaml
processing:
  embedding_model: "model_cache/multilingual-e5-large"
  spacy_model: "ru_core_news_lg"
qdrant:
  host: "localhost"
  port: 6333
```

## Проверка работы
**После запуска службы проверьте:**
- Доступность веб-интерфейса: http://localhost:8000
- API документация: http://localhost:8000/docs
- Логи службы: app.log и app_error.log

## Для работы с документами используйте:
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf"
```

### Поддерживаемые форматы документов
- **PDF** (.pdf) - с OCR поддержкой
- **Word** (.docx, .doc)
- **Текст** (.txt)
- **Excel**
