# query.py (обновленная версия)
import json
from qdrant_client import QdrantClient
from qdrant_client.models import Filter
from sentence_transformers import SentenceTransformer
from utils.helpers import load_config, normalize_text

class RAGSystem:
    def __init__(self):
        self.config = load_config()
        self.client = QdrantClient(
            host=self.config['qdrant']['host'],
            port=self.config['qdrant']['port'],
            timeout=10
        )
        self.embedding_model = SentenceTransformer(
            self.config['processing']['embedding_model']
        )
        self.min_score = self.config['processing']['min_similarity']
    
    def search(self, query, top_k=5):
        try:
            # Векторизация запроса
            query_embedding = self.embedding_model.encode([normalize_text(query)])[0].tolist()
            
            results = self.client.search(
                collection_name=self.config['qdrant']['collection_name'],
                query_vector=query_embedding,
                limit=top_k,
                with_payload=True,
                score_threshold=self.min_score
            )
            
            if not results:
                return "По вашему запросу ничего не найдено."
            
            output = []
            for idx, result in enumerate(results, 1):
                payload = result.payload
                metadata = payload.get('metadata', {})
                
                # Формируем контекст с заголовками
                context = ""
                if metadata.get('chapter'):
                    context += f"Раздел: {metadata['chapter']}\n"
                if metadata.get('section'):
                    context += f"Подраздел: {metadata['section']}\n"
                
                context += f"Текст: {payload['text']}"
                
                output.append(
                    f"Результат #{idx}\n"
                    f"📄 Источник: {metadata.get('source', 'неизвестно')}\n"
                    f"📖 Страница: {metadata.get('page', 'N/A')}\n"
                    f"🔍 Сходство: {result.score:.4f}\n\n"
                    f"📝 Контекст:\n{context}\n"
                    f"{'='*50}"
                )
            
            return "\n\n".join(output) if output else "Найдены результаты, но без текстового содержимого"
        
        except Exception as e:
            return f"Ошибка поиска: {str(e)}"

    def debug_check_data(self):
        """Метод для проверки сохраненных данных"""
        try:
            records = self.client.scroll(
                collection_name=self.config['qdrant']['collection_name'],
                limit=3,
                with_payload=True
            )[0]
            
            print("\nПроверка первых 3 записей в Qdrant:")
            for record in records:
                print(f"\nID: {record.id}")
                print(f"Текст: {record.payload.get('text', 'НЕТ ТЕКСТА')[:200]}...")
                print(f"Метаданные: {json.dumps(record.payload.get('metadata', {}), indent=2, ensure_ascii=False)}")
        
        except Exception as e:
            print(f"Ошибка проверки данных: {str(e)}")

if __name__ == "__main__":
    rag = RAGSystem()
    
    # Для проверки данных раскомментируйте:
    # rag.debug_check_data()
    
    while True:
        query = input("\n🔍 Ваш вопрос (или 'exit' для выхода): ")
        if query.lower() == 'exit':
            break
        
        results = rag.search(query)
        print("\nРезультаты поиска:")
        print(results)