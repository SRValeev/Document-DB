import json
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from utils.helpers import load_config, normalize_text

class RAGSystem:
    def __init__(self):
        self.config = load_config()
        self.client = QdrantClient(
            host=self.config['qdrant']['host'],
            port=self.config['qdrant']['port']
        )
        self.embedding_model = SentenceTransformer(
            self.config['processing']['embedding_model']
        )
    
    def search(self, query, top_k=5):
        # Векторизация запроса
        query_embedding = self.embedding_model.encode([normalize_text(query)])[0]
        
        # Поиск в векторной БД
        results = self.client.search(
            collection_name=self.config['qdrant']['collection_name'],
            query_vector=query_embedding.tolist(),
            limit=top_k,
            with_payload=True
        )
        
        # Форматирование результатов
        context = "\n\n".join([
            f"Источник: {result.payload['metadata']['source']} (Страница: {result.payload['metadata']['page']})\n"
            f"Контекст: {result.payload['text']}\n"
            f"Сходство: {result.score:.4f}"
            for result in results
        ])
        
        return context
    
    def rag_query(self, query, llm_api=None):
        context = self.search(query)
        
        # Если подключена LLM API
        if llm_api:
            prompt = f"""
            Используй следующий контекст, чтобы ответить на вопрос в конце.
            Если не знаешь ответ, скажи 'Не нашел информации'.
            
            Контекст:
            {context}
            
            Вопрос: {query}
            """
            return llm_api.generate(prompt)
        
        return context

if __name__ == "__main__":
    rag = RAGSystem()
    
    while True:
        query = input("\nВаш вопрос (или 'exit' для выхода): ")
        if query.lower() == 'exit':
            break
        
        results = rag.search(query)
        print("\nРезультаты поиска:")
        print(results)