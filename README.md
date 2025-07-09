
1. в scripts есть install.bat он кривой, Ghostscript пока больше не нужен.
2. в requirements большинство использованных библиотек но возможно не все.
3. очень желательно использовать python -m venv .venv
3. Эти модели нужно качать ручками python -m spacy download ru_core_news_md
4. Нужно отдельно скачать и поставить qdrant.exe качать отсюда https://github.com/qdrant/qdrant/releases/download/v1.14.1/qdrant-x86_64-pc-windows-msvc.zip
5. БД qdrant.exe поднимаем в отдельном терминале, есить есть жалание там есть докер образы этой СУБД
6. Каталожек Processed нужно очищать вручную ну или дописать очистку в ingest.py
7. Пока на сегодня всё.