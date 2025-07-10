#!/bin/bash
# Установка RAG Document Assistant для Linux/macOS

# Настройки
VENV_DIR=".venv"
QDRANT_VERSION="v1.14.1"
QDRANT_URL="https://github.com/qdrant/qdrant/releases/download/$QDRANT_VERSION/qdrant-x86_64-unknown-linux-gnu.tar.gz"

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "Ошибка: Python3 не установлен"
    exit 1
fi

# Создание виртуального окружения
echo -e "\033[36mСоздание виртуального окружения...\033[0m"
python3 -m venv $VENV_DIR
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Ошибка создания виртуального окружения"
    exit 1
fi

# Активация venv
echo -e "\033[36mАктивация окружения...\033[0m"
source "$VENV_DIR/bin/activate"

# Установка зависимостей
echo -e "\033[36mУстановка Python-зависимостей...\033[0m"
pip install --upgrade pip
pip install -r requirements/requirements.txt

# Установка spaCy моделей
echo -e "\033[36mУстановка моделей spaCy...\033[0m"
python -m spacy download ru_core_news_md
python -m spacy download ru_core_news_lg

# Установка Qdrant
echo -e "\033[36mУстановка Qdrant...\033[0m"
if [ ! -f "qdrant/qdrant" ]; then
    mkdir -p qdrant
    wget $QDRANT_URL -O qdrant.tar.gz
    tar -xzf qdrant.tar.gz -C qdrant
    rm qdrant.tar.gz
fi

# Установка Tesseract (для OCR)
echo -e "\033[36mУстановка Tesseract...\033[0m"
if command -v apt-get &> /dev/null; then
    sudo apt-get install -y tesseract-ocr tesseract-ocr-rus
elif command -v yum &> /dev/null; then
    sudo yum install -y tesseract tesseract-langpack-rus
elif command -v brew &> /dev/null; then
    brew install tesseract tesseract-lang
fi

# Установка Camelot
echo -e "\033[36mУстановка Camelot...\033[0m"
pip install camelot-py[base]
pip install opencv-python

# Создание директорий
echo -e "\033[36mСоздание рабочих директорий...\033[0m"
mkdir -p data processed temp qdrant/storage log

echo -e "\n\033[32mУстановка завершена!\033[0m\nДля запуска используйте: ./Scripts/startup.sh"