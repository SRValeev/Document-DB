# 🚨 БЫСТРОЕ ИСПРАВЛЕНИЕ ОШИБОК ЗАВИСИМОСТЕЙ

## Проблема
```
ERROR: Could not find a version that satisfies the requirement ru_core_news_md
ERROR: Ignored versions that require different python version
```

## ⚡ Быстрое решение

### 1. Проверьте версию Python
```bash
python --version
```

### 2. Выберите правильный файл зависимостей

**Для Python 3.8-3.11:**
```bash
pip install -r requirements.txt
```

**Для Python 3.12+:**
```bash
pip install -r requirements-python312.txt
```

### 3. Установите SpaCy модель отдельно
```bash
# НИКОГДА не добавляйте ru_core_news_md в requirements.txt!
# Это НЕ PyPI пакет!

# Правильная установка:
python -m spacy download ru_core_news_lg
```

### 4. Проверьте установку
```bash
python -c "import spacy; nlp = spacy.load('ru_core_news_lg'); print('✅ SpaCy OK')"
python -c "import fastapi, torch, sentence_transformers; print('✅ All packages OK')"
```

## 📝 Для офлайн дистрибутива

```bash
# Установите зависимости для сборки
pip install -r scripts/build_offline_requirements.txt

# Запустите сборку (исправленная версия)
build_offline_dist.bat
```

## ❗ Важно
- **ru_core_news_md НЕ PyPI пакет** - его нельзя добавлять в requirements.txt
- **Используйте ru_core_news_lg** для офлайн дистрибутива (лучше качество)
- **Python 3.12+** требует специальный файл зависимостей

**Проблемы решены!** ✅