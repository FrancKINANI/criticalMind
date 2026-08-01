"""
Abstraction du provider LLM interchangeable (cloud / edge).

Permet de basculer entre un provider cloud compatible avec l'API OpenAI
(OpenAI, OpenRouter, Mistral, vLLM, ...) et un provider edge local (Ollama)
sans changer le code appelant, via la table ``settings`` en base de données
(voir ``GET/PUT /api/admin/llm-settings``) ou via des variables d'environnement.

Choix documenté (divergence volontaire avec smart_notes) :
ce repo reste 100% Python/Flask et utilise Ollama en edge plutôt que le SDK
QVAC (Node) de smart_notes — voir README.md pour la justification.
"""

import logging
import os
from abc import ABC, abstractmethod

import requests

logger = logging.getLogger(__name__)

# Réglages par défaut par provider (repli si rien n'est configuré en DB/env)
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
    """Erreur d'appel au provider LLM (réseau, API, clé manquante...)."""


class LLMProvider(ABC):
    """Interface commune des providers LLM (cloud ou edge)."""

    name = 'base'

    def __init__(self, base_url, model_name, api_key=None):
        self.base_url = (base_url or '').rstrip('/')
        self.model_name = model_name
        self.api_key = api_key

    @property
    def is_edge(self):
        """True si le provider est un modèle local (qualité non garantie)."""
        return False

    @abstractmethod
    def generate(self, prompt, system=None, temperature=0.7, max_tokens=300):
        """Génère une réponse texte pour le prompt donné."""
        raise NotImplementedError

    def __repr__(self):
        return f'<{self.__class__.__name__} model={self.model_name}>'


class OpenAICompatibleProvider(LLMProvider):
    """Provider compatible API OpenAI (``/chat/completions``).

    Généralise l'ancien appel ``openai.OpenAI()`` en dur (learning.py) à une
    ``base_url`` configurable : OpenAI, OpenRouter, Mistral, vLLM, etc.
    Implémenté avec ``requests`` (déjà dans requirements.txt) plutôt que le
    SDK ``openai`` (non déclaré ni installé) — ce qui corrige au passage le
    ``ModuleNotFoundError: No module named 'openai'`` qui empêchait l'app de
    démarrer.
    """

    name = 'openai'

    def generate(self, prompt, system=None, temperature=0.7, max_tokens=300):
        if not self.api_key:
            raise LLMProviderError(
                'OPENAI_API_KEY manquante pour le provider OpenAI-compatible'
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
            logger.error('Appel OpenAI-compatible échoué (%s): %s', url, exc)
            raise LLMProviderError(str(exc)) from exc
        except (KeyError, IndexError, ValueError) as exc:
            logger.error('Réponse OpenAI-compatible inattendue (%s): %s', url, exc)
            raise LLMProviderError(str(exc)) from exc


class OllamaProvider(LLMProvider):
    """Provider edge local via l'API HTTP d'Ollama (défaut : http://localhost:11434).

    Utilise l'endpoint compatible OpenAI ``/v1/chat/completions`` exposé par
    Ollama pour conserver exactement le même format de requête que le cloud.
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
                'Appel Ollama échoué (Ollama est-il lancé sur %s ?): %s', url, exc
            )
            raise LLMProviderError(str(exc)) from exc
        except (KeyError, IndexError, ValueError) as exc:
            logger.error('Réponse Ollama inattendue (%s): %s', url, exc)
            raise LLMProviderError(str(exc)) from exc


def get_default_settings():
    """Réglages par défaut du provider actif (env > constantes)."""
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
    """Réglages LLM depuis la table ``settings`` (repli env/constantes)."""
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
    except Exception as exc:  # table absente, hors contexte d'app, etc.
        logger.warning(
            'Réglages LLM indisponibles en DB (%s), utilisation des défauts env.', exc
        )
    return get_default_settings()


def get_llm_provider():
    """Factory : renvoie le provider LLM configuré (cloud ou edge)."""
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
    # Provider inconnu : repli sur OpenAI-compatible par défaut
    logger.warning('Provider LLM inconnu "%s", repli sur OpenAI-compatible.', provider)
    return OpenAICompatibleProvider(
        settings['base_url'],
        settings['model_name'],
        api_key=os.environ.get('OPENAI_API_KEY'),
    )
