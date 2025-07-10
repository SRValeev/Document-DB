#!/bin/bash
# Запуск RAG Document Assistant для Linux/macOS

# Настройки
QDRANT_PORT=6333
UVICORN_PORT=8000

# Проверка Qdrant
if [ ! -f "qdrant/qdrant" ]; then
    echo -e "\033[31mОшибка: Qdrant не установлен. Сначала выполните install.sh\033[0m"
    exit 1
fi

# Проверка виртуального окружения
if [ ! -f ".venv/bin/activate" ]; then
    echo -e "\033[31mОшибка: Виртуальное окружение не найдено\033[0m"
    exit 1
fi

# Очистка временных файлов
echo -e "\033[36mОчистка временных файлов...\033[0m"
rm -rf temp/*
mkdir -p temp

# Запуск Qdrant в фоне
echo -e "\033[36mЗапуск Qdrant...\033[0m"
./qdrant/qdrant --storage-snapshot-interval-sec 60 &

# Ожидание старта Qdrant
qdrant_ready=false
attempts=0
while [ "$qdrant_ready" = false ] && [ $attempts -lt 10 ]; do
    if curl -s "http://localhost:$QDRANT_PORT/" > /dev/null; then
        qdrant_ready=true
    else
        sleep 3
        attempts=$((attempts+1))
    fi
done

if [ "$qdrant_ready" = false ]; then
    echo -e "\033[31mОшибка: Qdrant не запустился\033[0m"
    exit 1
fi

# Активация venv и запуск сервиса
echo -e "\033[36mЗапуск сервиса...\033[0m"
source ".venv/bin/activate"
uvicorn main:app --host 0.0.0.0 --port $UVICORN_PORT

echo -e "\033[33mСервис остановлен\033[0m"