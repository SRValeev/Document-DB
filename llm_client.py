import httpx
import logging
from typing import Dict, Optional
from utils.helpers import load_config

class LLMClient:
    def __init__(self):
        self.config = load_config().get('llm', {})
        self.client = httpx.AsyncClient(timeout=60.0)
        self._validate_config()

    def _validate_config(self):
        """Проверка обязательных параметров конфигурации"""
        required_keys = ['api_url', 'model']
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required LLM config key: {key}")

    async def generate_response(self, prompt: str, context: str = "", **kwargs) -> str:
        """Генерация ответа с использованием LLM"""
        try:
            messages = [
                {"role": "system", "content": self.config.get('system_prompt', '')},
                {"role": "user", "content": f"{context}\n\n{prompt}"}
            ]
            
            # Базовые параметры из конфига
            payload = {
                "model": self.config['model'],
                "messages": messages,
                "temperature": float(kwargs.get('temperature', self.config.get('temperature', 0.7))),
                "max_tokens": int(kwargs.get('max_tokens', self.config.get('max_tokens', 1000))),
                "top_p": float(kwargs.get('top_p', self.config.get('top_p', 0.9))),
                "frequency_penalty": float(kwargs.get('frequency_penalty', self.config.get('frequency_penalty', 0.2))),
                "presence_penalty": float(kwargs.get('presence_penalty', self.config.get('presence_penalty', 0.2)))
            }
            
            response = await self.client.post(
                f"{self.config['api_url']}/chat/completions",
                json=payload
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            logging.error(f"LLM request failed: {str(e)}")
            return "Не удалось получить ответ от LLM"

    async def close(self):
        """Закрытие клиента"""
        await self.client.aclose()

# Синглтон-экземпляр
llm_client = LLMClient()