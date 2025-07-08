@echo off
REM Установка Python-зависимостей для Windows
pip install -r requirements.txt
pip install python-docx qdrant-client tqdm pyyaml pdfminer.six

REM Установка spaCy модели для русского языка
python -m spacy download ru_core_news_md

REM Установка Ghostscript (требуется для Camelot)
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10051/gs10051w64.exe' -OutFile 'gsinstaller.exe'"
gsinstaller.exe /S
del gsinstaller.exe

echo Установка не завершена! Не запускайте start.bat для начала работы.
pause