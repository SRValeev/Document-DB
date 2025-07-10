#llm_client.py
import httpx
import logging
from utils.helpers import load_config

class LLMClient:
    def __init__(self):
        self.config = load_config().get('llm', {})
        self.logger = logging.getLogger(__name__)
        self.client = httpx.AsyncClient(timeout=60.0)
        self._validate_config()

    def _validate_config(self):
        required_keys = ['api_url', 'model']
        for key in required_keys:
            if key not in self.config:
                error_msg = f"Missing required LLM config key: {key}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)

    async def generate_response(self, prompt: str, context: str = "", **kwargs):
        try:
            messages = [
                {"role": "system", "content": self.config.get('system_prompt', '')},
                {"role": "user", "content": f"{context}\n\n{prompt}" if context else prompt}
            ]
            
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
            
            result = response.json()
            self.logger.info("LLM response generated successfully")
            return result['choices'][0]['message']['content']
            
        except Exception as e:
            self.logger.error(f"LLM request failed: {str(e)}", exc_info=True)
            return "Не удалось получить ответ от LLM"

    async def close(self):
        try:
            await self.client.aclose()
            self.logger.info("LLM client closed")
        except Exception as e:
            self.logger.error(f"Error closing LLM client: {str(e)}")

# Синглтон-экземпляр
llm_client = LLMClient()