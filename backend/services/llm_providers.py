from abc import ABC, abstractmethod
from typing import Any, List

import requests
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.embeddings import BaseEmbedding
from llama_index.llms.ollama import Ollama


class _FlexOpenAIEmbedding(BaseEmbedding):
    """Embedding for OpenAI-compatible APIs — accepts any model name without validation."""
    _base_url: str = PrivateAttr()
    _headers: Any = PrivateAttr()

    def __init__(self, model: str, api_key: str, api_base: str, **kwargs):
        super().__init__(model_name=model, **kwargs)
        self._base_url = (api_base if api_base.endswith('/v1') else f"{api_base}/v1") + '/embeddings'
        self._headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

    def _embed(self, text: str) -> List[float]:
        resp = requests.post(
            self._base_url,
            headers=self._headers,
            json={'model': self.model_name, 'input': text},
            timeout=120
        )
        resp.raise_for_status()
        return resp.json()['data'][0]['embedding']

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._embed(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._embed(text)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._embed(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._embed(text)


class LLMProvider(ABC):
    REQUIRED_FIELDS = []  # campos que el usuario debe rellenar al crear este tipo de servidor

    @abstractmethod
    def build_llm(self, model: str, system_prompt: str = '', temperature: float = None):
        """Devuelve una instancia LLM de LlamaIndex lista para usar."""

    @abstractmethod
    def get_models(self) -> list:
        """Devuelve los modelos disponibles en este proveedor."""

    @abstractmethod
    def build_embedding(self, model: str):
        """Devuelve una instancia de embeddings de LlamaIndex lista para usar."""

    def validate(self) -> bool:
        """Comprueba que el servidor es alcanzable. Por defecto, se asume válido."""
        return True


class OllamaProvider(LLMProvider):
    REQUIRED_FIELDS = ['base_url']

    def __init__(self, base_url: str, **_):
        self.base_url = base_url.rstrip('/')

    def build_llm(self, model: str, system_prompt: str = '', temperature: float = None):
        return Ollama(
            model=model,
            base_url=self.base_url,
            request_timeout=600.0,
            system_prompt=system_prompt or None,
            context_window=8000,
            temperature=temperature if temperature is not None else 0.1
        )

    def get_models(self) -> list:
        try:
            resp = requests.get(f'{self.base_url}/api/tags', timeout=5)
            resp.raise_for_status()
            return [m['name'] for m in resp.json().get('models', [])]
        except Exception:
            return []

    def build_embedding(self, model: str):
        from llama_index.embeddings.ollama import OllamaEmbedding
        return OllamaEmbedding(model_name=model, base_url=self.base_url)

    def validate(self) -> bool:
        try:
            resp = requests.get(f'{self.base_url}/api/tags', timeout=5)
            resp.raise_for_status()
            return True
        except Exception:
            return False


class GeminiProvider(LLMProvider):
    REQUIRED_FIELDS = ['api_key']
    AVAILABLE_MODELS = [
        'gemini-2.5-flash-lite',
        'gemini-3.1-flash-lite'
    ]

    def __init__(self, api_key: str, **_):
        self.api_key = api_key

    def build_llm(self, model: str, system_prompt: str = '', temperature: float = None):
        from llama_index.llms.gemini import Gemini
        return Gemini(
            model=model,
            api_key=self.api_key,
            system_prompt=system_prompt or None,
            temperature=temperature if temperature is not None else 0.1
        )

    def get_models(self) -> list:
        return self.AVAILABLE_MODELS

    def build_embedding(self, model: str):
        from llama_index.embeddings.gemini import GeminiEmbedding
        return GeminiEmbedding(model_name=model, api_key=self.api_key)


class OpenAILikeProvider(LLMProvider):
    REQUIRED_FIELDS = ['base_url', 'api_key']

    def __init__(self, base_url: str, api_key: str, **_):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

    def build_llm(self, model: str, system_prompt: str = '', temperature: float = None):
        from llama_index.llms.openai_like import OpenAILike
        return OpenAILike(
            model=model,
            api_key=self.api_key,
            api_base=self.base_url,
            temperature=temperature if temperature is not None else 0.1,
            system_prompt=system_prompt or None,
            is_chat_model=True,
            context_window=8000,
        )

    def get_models(self) -> list:
        try:
            resp = requests.get(
                f'{self.base_url}/v1/models',
                headers={'Authorization': f'Bearer {self.api_key}'},
                timeout=5
            )
            resp.raise_for_status()
            return [m['id'] for m in resp.json().get('data', [])]
        except Exception:
            return []

    def build_embedding(self, model: str):
        return _FlexOpenAIEmbedding(model=model, api_key=self.api_key, api_base=self.base_url)

    def validate(self) -> bool:
        try:
            resp = requests.get(
                f'{self.base_url}/v1/models',
                headers={'Authorization': f'Bearer {self.api_key}'},
                timeout=5
            )
            resp.raise_for_status()
            return True
        except Exception:
            return False


PROVIDERS = {
    'ollama': OllamaProvider,
    'gemini': GeminiProvider,
    'openai': OpenAILikeProvider,
}


def get_provider(server_config: dict) -> LLMProvider:
    provider_type = server_config.get('type')
    cls = PROVIDERS.get(provider_type)
    if not cls:
        raise ValueError(f'Unknown provider type: {provider_type}')
    return cls(**server_config)