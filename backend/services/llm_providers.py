from abc import ABC, abstractmethod
import requests
from llama_index.llms.ollama import Ollama


class LLMProvider(ABC):
    REQUIRED_FIELDS = []  # campos que el usuario debe rellenar al crear este tipo de servidor

    @abstractmethod
    def build_llm(self, model: str, system_prompt: str = ''):
        """Devuelve una instancia LLM de LlamaIndex lista para usar."""

    @abstractmethod
    def get_models(self) -> list:
        """Devuelve los modelos disponibles en este proveedor."""

    def validate(self) -> bool:
        """Comprueba que el servidor es alcanzable. Por defecto, se asume válido."""
        return True


class OllamaProvider(LLMProvider):
    REQUIRED_FIELDS = ['base_url']

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

    def build_llm(self, model: str, system_prompt: str = ''):
        from llama_index.llms.gemini import Gemini
        return Gemini(
            model=model,
            api_key=self.api_key,
            system_prompt=system_prompt or None
        )

    def get_models(self) -> list:
        return self.AVAILABLE_MODELS


class OpenAILikeProvider(LLMProvider):
    REQUIRED_FIELDS = ['base_url', 'api_key']

    def __init__(self, base_url: str, api_key: str, **_):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

    def build_llm(self, model: str, system_prompt: str = ''):
        from llama_index.llms.openai_like import OpenAILike
        return OpenAILike(
            model=model,
            api_key=self.api_key,
            api_base=self.base_url,
            temperature=0.1,
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