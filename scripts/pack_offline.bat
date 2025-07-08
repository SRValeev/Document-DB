@echo off
SETLOCAL

REM Создание wheelhouse со всеми зависимостями
mkdir wheelhouse 2>nul
pip download -r requirements\requirements.txt -d wheelhouse

REM Копирование spaCy моделей
python -m spacy download ru_core_news_md --direct --user
python -m spacy download ru_core_news_lg --direct --user
xcopy "%USERPROFILE%\AppData\Local\spacy" .\wheelhouse\spacy_models /E /I /Y

echo Оффлайн-пакет создан в wheelhouse и spacy_models
pause