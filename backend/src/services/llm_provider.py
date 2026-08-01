"""
Interchangeable LLM provider abstraction (cloud / edge).

Allows switching between a cloud provider compatible with the OpenAI API
(OpenAI, OpenRouter, Mistral, vLLM, ...) and a local edge provider (Ollama)
without changing the calling code, via the ``settings`` table in the database
(see ``GET/PUT /api/admin/llm-settings``) or via environment variables.

Documented choice (intentional divergence from smart_notes):
this repo remains 100% Python/Flask and uses Ollama for edge rather than the
QVAC (Node) SDK from smart_notes — see README.md for the justification.
"""

import logging
import os
from abc import ABC, abstractmethod

import requests

logger = logging.getLogger(__name__)

# Default settings per provider (fallback if nothing is configured in DB/env)
PROVIDER_DEFAULTS = {
    'openai': {
        'base_url': 'https://api.openai.com/v1',
        'model_name': 'gpt-3.5-turbo',
    },
    'ollama': {
        'base_url': 'http://localhost:11434',
        'model_name': 'llama3.2:1b',
    },
}

DEFAULT_PROVIDER = os.environ.get('LLM_PROVIDER', 'openai').lower()


class LLMProviderError(Exception):
    """Error calling the LLM provider (network, API, missing key...)."""


class LLMProvider(ABC):
    """Common interface for LLM providers (cloud or edge)."""

    name = 'base'

    def __init__(self, base_url, model_name, api_key=None):
        self.base_url = (base_url or '').rstrip('/')
        self.model_name = model_name
        self.api_key = api_key

    @property
    def is_edge(self):
        """True if the provider is a local model (quality not guaranteed)."""
        return False

    @abstractmethod
    def generate(self, prompt, system=None, temperature=0.7, max_tokens=300):
        """Generates a text response for the given prompt."""
        raise NotImplementedError

    def __repr__(self):
        return f'<{self.__class__.__name__} model={self.model_name}>'


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI API-compatible provider (``/chat/completions``).

    Generalizes the old hardcoded ``openai.OpenAI()`` call (learning.py) to a
    configurable ``base_url``: OpenAI, OpenRouter, Mistral, vLLM, etc.
    Implemented with ``requests`` (already in requirements.txt) rather than the
    ``openai`` SDK (not declared nor installed) — which also fixes the
    ``ModuleNotFoundError: No module named 'openai'`` that prevented the app from
    starting.
    """

    name = 'openai'

    def generate(self, prompt, system=None, temperature=0.7, max_tokens=300):
        if not self.api_key:
            raise LLMProviderError(
                'OPENAI_API_KEY missing for the OpenAI-compatible provider'
            )

        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})

        url = f'{self.base_url}/chat/completions'
        try:
            response = requests.post(
                url,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': self.model_name,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens,
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except requests.RequestException as exc:
            logger.error('OpenAI-compatible call failed (%s): %s', url, exc)
            raise LLMProviderError(str(exc)) from exc
        except (KeyError, IndexError, ValueError) as exc:
            logger.error('Unexpected OpenAI-compatible response (%s): %s', url, exc)
            raise LLMProviderError(str(exc)) from exc


class OllamaProvider(LLMProvider):
    """Local edge provider via Ollama's HTTP API (default: http://localhost:11434).

    Uses the OpenAI-compatible ``/v1/chat/completions`` endpoint exposed by
    Ollama to maintain exactly the same request format as the cloud provider.
    """

    name = 'ollama'

    @property
    def is_edge(self):
        return True

    def generate(self, prompt, system=None, temperature=0.7, max_tokens=300):
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})

        url = f'{self.base_url}/v1/chat/completions'
        try:
            response = requests.post(
                url,
                json={
                    'model': self.model_name,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens,
                    'stream': False,
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except requests.RequestException as exc:
            logger.error(
                'Ollama call failed (is Ollama running on %s?): %s', url, exc
            )
            raise LLMProviderError(str(exc)) from exc
        except (KeyError, IndexError, ValueError) as exc:
            logger.error('Unexpected Ollama response (%s): %s', url, exc)
            raise LLMProviderError(str(exc)) from exc


def get_default_settings():
    """Default settings of the active provider (env > constants)."""
    provider = DEFAULT_PROVIDER
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS['openai'])
    base_url = os.environ.get(
        'LLM_BASE_URL', os.environ.get('OPENAI_API_BASE')
    ) or defaults['base_url']
    model_name = os.environ.get(
        'LLM_MODEL', os.environ.get('OPENAI_MODEL')
    ) or defaults['model_name']
    return {
        'provider': provider,
        'base_url': base_url,
        'model_name': model_name,
    }


def get_llm_settings():
    """LLM settings from the ``settings`` table (env/constants fallback)."""
    try:
        from src.models.setting import Setting

        setting = Setting.query.order_by(Setting.id.asc()).first()
        if setting:
            provider = (setting.provider or DEFAULT_PROVIDER).lower()
            defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS['openai'])
            env_base_url = os.environ.get(
                'LLM_BASE_URL', os.environ.get('OPENAI_API_BASE')
            ) or defaults['base_url']
            env_model = os.environ.get(
                'LLM_MODEL', os.environ.get('OPENAI_MODEL')
            ) or defaults['model_name']
            return {
                'provider': provider,
                'base_url': setting.base_url or env_base_url,
                'model_name': setting.model_name or env_model,
            }
    except Exception as exc:  # missing table, outside app context, etc.
        logger.warning(
            'LLM settings unavailable in DB (%s), using env defaults.', exc
        )
    return get_default_settings()


def get_llm_provider():
    """Factory: returns the configured LLM provider (cloud or edge)."""
    settings = get_llm_settings()
    provider = settings['provider'].lower()

    if provider == 'ollama':
        return OllamaProvider(settings['base_url'], settings['model_name'])
    if provider == 'openai':
        return OpenAICompatibleProvider(
            settings['base_url'],
            settings['model_name'],
            api_key=os.environ.get('OPENAI_API_KEY'),
        )
    # Unknown provider: fall back to the default OpenAI-compatible provider
    logger.warning('Unknown LLM provider "%s", falling back to OpenAI-compatible.', provider)
    return OpenAICompatibleProvider(
        settings['base_url'],
        settings['model_name'],
        api_key=os.environ.get('OPENAI_API_KEY'),
    )
