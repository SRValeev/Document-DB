@echo off
REM Установка Python-зависимостей для Windows
pip install pymupdf camelot-py[base] langchain spacy sentence-transformers python-docx qdrant-client tqdm pyyaml pdfminer.six

REM Установка spaCy модели для русского языка
python -m spacy download ru_core_news_md

REM Установка Ghostscript (требуется для Camelot)
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10022/gs10022w64.exe' -OutFile 'gsinstaller.exe'"
gsinstaller.exe /S
del gsinstaller.exe

REM Добавление Ghostscript в PATH
setx /M PATH "%PATH%;C:\Program Files\gs\gs10.02.2\bin"

echo Установка завершена! Запустите start.bat для начала работы.
pause