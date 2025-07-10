import logging
import re
import numpy as np
from typing import List, Dict, Any
from sklearn.metrics.pairwise import cosine_similarity
from nltk.corpus import stopwords
import nltk

# Загрузка стоп-слов при импорте
try:
    nltk.download('stopwords', quiet=True)
    STOPWORDS_RU = set(stopwords.words('russian'))
except Exception as e:
    logging.warning(f"Не удалось загрузить стоп-слова: {str(e)}")
    STOPWORDS_RU = set()

class ContextBuilder:
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация построителя контекста
        
        Args:
            config: Конфигурация из config.yaml
        """
        self.config = config.get('context', {})
        self.logger = logging.getLogger(__name__)
        
        # Параметры из конфига
        self.diversity_factor = self.config.get('diversity_factor', 0.3)
        self.min_relevance = self.config.get('min_relevance', 0.65)
        self.max_duplicate_distance = self.config.get('max_duplicate_distance', 0.2)
        self.max_chunks = self.config.get('max_chunks', 5)
        self.clean_stopwords = self.config.get('clean_stopwords', True)

    def build_context(self, query_embedding: List[float], qdrant_results: List) -> str:
        """Версия с полной отладкой"""
        self.logger.debug(f"Начало build_context, получено {len(qdrant_results)} результатов")
        
        if not qdrant_results:
            self.logger.warning("Пустой список результатов от Qdrant")
            return ""

        try:
            # Проверка структуры результатов
            sample_result = qdrant_results[0]
            if not hasattr(sample_result, 'payload'):
                self.logger.error("Некорректная структура результатов: отсутствует payload")
                return ""
                
            # Фильтрация по релевантности
            filtered = [r for r in qdrant_results if r.score >= self.min_relevance]
            self.logger.debug(f"После фильтрации осталось {len(filtered)} результатов")
            
            if not filtered:
                self.logger.warning("Нет результатов, прошедших порог релевантности")
                return ""
                
            # Проверка наличия векторов
            if not all(hasattr(r, 'vector') for r in filtered):
                self.logger.warning("Часть результатов не содержит векторов, возвращаем топ по score")
                return self._format_context([r for r in filtered[:self.max_chunks]])
                
            # MMR выборка
            selected = self._mmr_selection(query_embedding, filtered)
            self.logger.debug(f"Выбрано {len(selected)} чанков после MMR")
            
            return self._format_context(selected)
            
        except Exception as e:
            self.logger.error(f"Ошибка построения контекста: {str(e)}", exc_info=True)
            return ""

    def _format_context(self, results: List) -> str:
        """Форматирование отобранных результатов"""
        context_parts = []
        seen_hashes = set()
        
        for result in results:
            try:
                payload = result.payload
                if not payload or 'text' not in payload:
                    continue
                    
                text = payload['text']
                clean_text = self._clean_text(text) if self.clean_stopwords else text
                text_hash = self._text_hash(clean_text)
                
                if text_hash in seen_hashes:
                    continue
                    
                seen_hashes.add(text_hash)
                
                metadata = payload.get('metadata', {})
                context_parts.append(
                    f"### {metadata.get('source', 'Документ')}\n"
                    f"Страница: {metadata.get('page', 'N/A')}\n"
                    f"Релевантность: {result.score:.2f}\n"
                    f"{clean_text}\n"
                    f"{'-'*40}\n"
                )
            except Exception as e:
                self.logger.warning(f"Ошибка форматирования чанка: {str(e)}")
                
        return "\n".join(context_parts) if context_parts else ""

    def _mmr_selection(self, query_embedding: List[float], results: List) -> List:
        """
        Maximal Marginal Relevance выборка результатов
        
        Args:
            query_embedding: Вектор запроса
            results: Список результатов поиска
            
        Returns:
            Отсортированный список результатов с учетом релевантности и разнообразия
        """
        if len(results) <= 1:
            return results
            
        # Получаем векторы документов
        doc_vectors = [r.vector for r in results if hasattr(r, 'vector')]
        if not doc_vectors:
            return results[:self.max_chunks]
        
        # Сходство с запросом
        query_sim = cosine_similarity([query_embedding], doc_vectors)[0]
        
        # Попарное сходство между документами
        doc_sim = cosine_similarity(doc_vectors)
        
        # MMR выборка
        selected = []
        remaining = list(range(len(results)))
        
        # Первый документ - самый релевантный
        selected.append(np.argmax(query_sim))
        remaining.remove(selected[0])
        
        while remaining and len(selected) < self.max_chunks:
            mmr_scores = []
            for i in remaining:
                rel_score = query_sim[i]
                max_sim = max([doc_sim[i][j] for j in selected]) if selected else 0
                mmr_score = (self.diversity_factor * rel_score - 
                            (1 - self.diversity_factor) * max_sim)
                mmr_scores.append((i, mmr_score))
            
            # Выбираем документ с максимальным MMR
            best_idx = max(mmr_scores, key=lambda x: x[1])[0]
            selected.append(best_idx)
            remaining.remove(best_idx)
        
        return [results[i] for i in selected]

    def _clean_text(self, text: str) -> str:
        """
        Очистка текста от мусора и стоп-слов
        
        Args:
            text: Исходный текст
            
        Returns:
            Очищенный текст
        """
        # Удаление специальных символов
        text = re.sub(r'[^\w\s.,:;!?()-]', ' ', text)
        # Удаление лишних пробелов
        text = re.sub(r'\s+', ' ', text).strip()
        
        if not self.clean_stopwords:
            return text
            
        # Удаление стоп-слов
        words = text.split()
        clean_words = [w for w in words if w.lower() not in STOPWORDS_RU]
        return ' '.join(clean_words)

    def _text_hash(self, text: str, length: int = 100) -> int:
        """
        Генерация хэша для текста (проверка дубликатов)
        
        Args:
            text: Текст для хэширования
            length: Длина префикса для хэширования
            
        Returns:
            Числовой хэш
        """
        text_part = text[:length].lower().encode('utf-8')
        return hash(text_part)

    def _is_duplicate(self, text: str, seen_hashes: set) -> bool:
        """
        Проверка на дубликат по хэшу
        
        Args:
            text: Проверяемый текст
            seen_hashes: Множество уже встреченных хэшей
            
        Returns:
            True если текст является дубликатом
        """
        text_hash = self._text_hash(text)
        return text_hash in seen_hashes