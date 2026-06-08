from abc import ABC, abstractmethod
import requests
from llama_index.llms.ollama import Ollama


class LLMProvider(ABC):
    @abstractmethod
    def build_llm(self, model: str, system_prompt: str = ''):
        """Devuelve una instancia LLM de LlamaIndex lista para usar."""

    @abstractmethod
    def get_models(self) -> list:
        """Devuelve los modelos disponibles en este proveedor."""


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, **_):
        self.base_url = base_url.rstrip('/')

    def build_llm(self, model: str, system_prompt: str = ''):
        return Ollama(
            model=model,
            base_url=self.base_url,
            request_timeout=600.0,
            system_prompt=system_prompt or None,
            context_window=8000,
            temperature=0.1
        )

    def get_models(self) -> list:
        try:
            resp = requests.get(f'{self.base_url}/api/tags', timeout=5)
            resp.raise_for_status()
            return [m['name'] for m in resp.json().get('models', [])]
        except Exception:
            return []


class GeminiProvider(LLMProvider):
    AVAILABLE_MODELS = [
        'gemini-2.0-flash-lite',
        'gemini-2.5-flash-lite',
        'gemini-3.1-flash-lite'
    ]

    def __init__(self, api_key: str, **_):
        self.api_key = api_key

    def build_llm(self, model: str, system_prompt: str = ''):
        from llama_index.llms.gemini import Gemini
        return Gemini(
            model=model,
            api_key=self.api_key,
            system_prompt=system_prompt or None
        )

    def get_models(self) -> list:
        return self.AVAILABLE_MODELS


PROVIDERS = {
    'ollama': OllamaProvider,
    'gemini': GeminiProvider,
}


def get_provider(server_config: dict) -> LLMProvider:
    provider_type = server_config.get('type')
    cls = PROVIDERS.get(provider_type)
    if not cls:
        raise ValueError(f'Unknown provider type: {provider_type}')
    return cls(**server_config)