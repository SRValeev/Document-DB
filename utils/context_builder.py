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
            if not config or 'context' not in config:
                raise ValueError("Config is missing required 'context' section")
            
            self.config = config
            self.context_config = config.get('context', {})
            
            # Установка параметров по умолчанию
            self.diversity_factor = self.context_config.get('diversity_factor', 0.3)
            self.min_relevance = self.context_config.get('min_relevance', 0.65)
            self.max_chunks = self.context_config.get('max_chunks', 5)

    def build_context(self, query_embedding: List[float], qdrant_results: List) -> str:
        """Строит контекст строго по параметрам из config.yaml"""
        params = self.config['context']
        
        # Фильтрация по минимальной релевантности
        filtered = [
            r for r in qdrant_results 
            if r.score >= params['min_relevance']
        ]
        
        # MMR или простой топ
        if params.get('mmr_enabled', True):
            selected = self._mmr_selection(query_embedding, filtered)
        else:
            selected = sorted(filtered, key=lambda x: x.score, reverse=True)[:params['max_chunks']]
        
        # Форматирование
        context_parts = []
        for result in selected:
            payload = result.payload
            meta = payload.get('metadata', {})
            context_parts.append(
                f"[[{meta.get('source', 'Документ')}]]\n"
                f"Стр. {meta.get('page', '?')} | Релевантность: {result.score:.2f}\n"
                f"{payload.get('text', '')}"
            )
        
        return "\n\n".join(context_parts)

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
        """Maximal Marginal Relevance выборка результатов"""
        if len(results) <= 1:
            return results
            
        # Получаем векторы документов, фильтруя NaN
        doc_vectors = []
        valid_results = []
        
        for r in results:
            if hasattr(r, 'vector') and r.vector is not None:
                # Проверяем на NaN
                if not any(np.isnan(x) for x in r.vector):
                    doc_vectors.append(r.vector)
                    valid_results.append(r)
        
        if not doc_vectors:
            return results[:self.max_chunks]
        
        # Преобразуем в numpy array и проверяем форму
        doc_vectors = np.array(doc_vectors)
        query_embedding = np.array(query_embedding)
        
        # Проверяем размерности
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        if doc_vectors.ndim == 1:
            doc_vectors = doc_vectors.reshape(-1, 1)
        
        # Сходство с запросом
        query_sim = cosine_similarity(query_embedding, doc_vectors)[0]
        
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