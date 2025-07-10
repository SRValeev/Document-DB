
1. в scripts есть инсталяторы для bash и PS, просто инсталлятор лежит в корне install.bat он вышел немного станным.
2. в requirements большинство использованных библиотек но возможно не все.
3. очень желательно использовать python -m venv .venv
3. Эти модели нужно качать ручками python -m spacy download ru_core_news_md
4. Нужно отдельно скачать и поставить qdrant.exe качать отсюда https://github.com/qdrant/qdrant/releases/download/v1.14.1/qdrant-x86_64-pc-windows-msvc.zip
5. Нужна установка Ghostscript
6. БД qdrant.exe поднимаем в отдельном терминале, есить есть жалание там есть докер образы этой СУБД
7. Пока на сегодня всё.