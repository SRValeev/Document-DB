# RAG Document Assistant v2.0 🚀
## Перед запуском
- Создать виртуальное окружение python -m venv "%VENV_NAME%"
- Активировать виртуальное окружение.
**Установить зависимости, для запуска на минималках желательно использовать u_core_news_md и sentence-transformers/paraphrase-multilingual-mpnet-base-v2**
- pip install --upgrade pip
- python -m spacy download ru_core_news_md
- pip install -r requirements\requirements.txt

## Linux Deployment
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
SPACY_MODEL="ru_core_news_lg" python -m spacy download $SPACY_MODEL
```

# Сборка для переноса на комп без интернета.
- Для сборки архива необходимо запустить build_dist.bat, ниже что делать с собранным архивом.

## Требования к целевому серверу
- Установите Python 3.1+ (скачать оффлайн-установщик:
- https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe)
- Установите NSSM (Non-Sucking Service Manager):
- Скачать: https://nssm.cc/release/nssm-2.24.zip
- Распаковать и скопировать nssm.exe в C:\Windows\System32
- Установите Microsoft Visual C++ Redistributable (для зависимостей):
- Скачать: https://aka.ms/vs/17/release/vc_redist.x64.exe

## Последовательность установки на сервере
 - Распакуйте дистрибутив в C:\RAGDocumentAssistant
 - Запустите install.bat
 - Запустите service_install.bat

## Запустите службу:
```cmd
nssm start RAGDocumentAssistant_Service
```
## Проверьте логи:
- app.log - основной лог приложения
- app_error.log - ошибки

## Особенности конфигурации
- В config.yaml укажите:
```yaml
processing:
  embedding_model: "model_cache/multilingual-e5-large"
  spacy_model: "ru_core_news_lg"
qdrant:
  host: "localhost"
  port: 6333
```
## Управление службой
- Старт службы: nssm start RAGDocumentAssistant_Service
- Остановка: nssm stop RAGDocumentAssistant_Service
- Перезапуск: nssm restart RAGDocumentAssistant_Service
- Удаление: nssm remove RAGDocumentAssistant_Service confirm

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
