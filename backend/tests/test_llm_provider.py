import pytest
from unittest.mock import patch

from src.models import db
from src.models.setting import Setting
from src.services.llm_provider import (
    get_llm_provider,
    OpenAICompatibleProvider,
    OllamaProvider,
    LLMProviderError,
)
from src.routes.learning import evaluate_essay_with_ai


class TestLLMProviderFactory:
    """Tests de la factory de provider LLM (cloud/edge)."""

    def test_default_provider_is_openai_cloud(self, client):
        """Sans réglage en DB, le provider par défaut est OpenAI-compatible (cloud)."""
        with client.application.app_context():
            provider = get_llm_provider()
        assert isinstance(provider, OpenAICompatibleProvider)
        assert provider.is_edge is False

    def test_ollama_provider_when_configured(self, client):
        """Une ligne settings provider=ollama doit renvoyer un OllamaProvider (edge)."""
        with client.application.app_context():
            db.session.add(Setting(
                provider='ollama',
                base_url='http://localhost:11434',
                model_name='llama3.2:1b',
            ))
            db.session.commit()
            provider = get_llm_provider()

        assert isinstance(provider, OllamaProvider)
        assert provider.is_edge is True
        assert provider.model_name == 'llama3.2:1b'

    def test_ollama_fallback_defaults_when_fields_empty(self, client):
        """provider=ollama avec champs vides en DB : on prend les défauts ollama,
        pas les défauts du provider par défaut (openai)."""
        with client.application.app_context():
            db.session.add(Setting(provider='ollama', base_url=None, model_name=None))
            db.session.commit()
            provider = get_llm_provider()

        assert isinstance(provider, OllamaProvider)
        assert provider.base_url == 'http://localhost:11434'
        assert provider.model_name == 'llama3.2:1b'

    def test_provider_requires_api_key_for_openai(self, client):
        """Le provider OpenAI-compatible sans clé doit lever une erreur claire."""
        with client.application.app_context():
            provider = OpenAICompatibleProvider(
                'https://api.openai.com/v1', 'gpt-3.5-turbo', api_key=None
            )
            with pytest.raises(LLMProviderError):
                provider.generate('test')


class TestAdminLLMSettings:
    """Tests des endpoints admin /api/admin/llm-settings."""

    def test_get_llm_settings(self, client, auth_headers):
        response = client.get('/api/admin/llm-settings', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert 'settings' in data
        settings = data['settings']
        assert 'provider' in settings
        assert 'base_url' in settings
        assert 'model_name' in settings

    def test_update_llm_settings(self, client, auth_headers):
        response = client.put(
            '/api/admin/llm-settings',
            headers=auth_headers,
            json={
                'provider': 'ollama',
                'base_url': 'http://localhost:11434',
                'model_name': 'llama3.2:1b',
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['settings']['provider'] == 'ollama'
        assert data['settings']['model_name'] == 'llama3.2:1b'

        # La configuration est persistée
        response2 = client.get('/api/admin/llm-settings', headers=auth_headers)
        assert response2.status_code == 200
        assert response2.get_json()['settings']['provider'] == 'ollama'

    def test_update_llm_settings_partial_switch(self, client, auth_headers):
        """Bascule provider-only : les champs manquants prennent les défauts du
        provider ciblé (ollama), pas ceux du provider précédent (openai)."""
        response = client.put(
            '/api/admin/llm-settings',
            headers=auth_headers,
            json={'provider': 'ollama'},
        )
        assert response.status_code == 200
        settings = response.get_json()['settings']
        assert settings['provider'] == 'ollama'
        assert settings['base_url'] == 'http://localhost:11434'
        assert settings['model_name'] == 'llama3.2:1b'

    def test_update_llm_settings_invalid_provider(self, client, auth_headers):
        response = client.put(
            '/api/admin/llm-settings',
            headers=auth_headers,
            json={'provider': 'weird-provider'},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'provider' in data['error']

    def test_student_cannot_access_llm_settings(self, client, student_headers):
        response = client.get('/api/admin/llm-settings', headers=student_headers)
        assert response.status_code == 403
        data = response.get_json()
        assert 'Insufficient permissions' in data['error']


class TestEssayEvaluationWarning:
    """Tests du warning edge/ollama sur la correction d'essai (fonctionnalité payante)."""

    def test_evaluate_essay_falls_back_on_provider_error(self, client):
        """En cas d'erreur provider, repli sans crash et sans warning edge."""

        class FailingProvider:
            name = 'openai'
            model_name = 'gpt-3.5-turbo'
            is_edge = False

            def generate(self, prompt, system=None, temperature=0.7, max_tokens=300):
                raise LLMProviderError('boom')

        with client.application.app_context():
            with patch('src.routes.learning.get_llm_provider', return_value=FailingProvider()):
                feedback, points, warning = evaluate_essay_with_ai('Q', 'R', 'E', 10)

        assert 'non disponible' in feedback
        assert points == 5  # score par défaut (max_points // 2)
        assert warning is False

    def test_evaluate_essay_returns_edge_warning(self, client):
        """Avec un provider edge, le flag de warning doit être renvoyé."""

        class EdgeProvider:
            name = 'ollama'
            model_name = 'llama3.2:1b'
            is_edge = True

            def generate(self, prompt, system=None, temperature=0.7, max_tokens=300):
                return 'Score: 8/10\nCommentaires: Bon travail, continuez ainsi.'

        with client.application.app_context():
            with patch('src.routes.learning.get_llm_provider', return_value=EdgeProvider()):
                feedback, points, warning = evaluate_essay_with_ai('Q', 'R', 'E', 10)

        assert points == 8
        assert 'Bon travail' in feedback
        assert warning is True

    def test_evaluate_essay_no_warning_for_cloud(self, client):
        """Avec un provider cloud, aucun warning edge."""

        class CloudProvider:
            name = 'openai'
            model_name = 'gpt-3.5-turbo'
            is_edge = False

            def generate(self, prompt, system=None, temperature=0.7, max_tokens=300):
                return 'Score: 9/10\nCommentaires: Excellent.'

        with client.application.app_context():
            with patch('src.routes.learning.get_llm_provider', return_value=CloudProvider()):
                feedback, points, warning = evaluate_essay_with_ai('Q', 'R', 'E', 10)

        assert points == 9
        assert warning is False
