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
    """Tests of the LLM provider factory (cloud/edge)."""

    def test_default_provider_is_openai_cloud(self, client):
        """Without DB settings, the default provider is OpenAI-compatible (cloud)."""
        with client.application.app_context():
            provider = get_llm_provider()
        assert isinstance(provider, OpenAICompatibleProvider)
        assert provider.is_edge is False

    def test_ollama_provider_when_configured(self, client):
        """A settings row with provider=ollama must return an OllamaProvider (edge)."""
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
        """provider=ollama with empty DB fields: the ollama defaults are used,
        not the defaults of the default provider (openai)."""
        with client.application.app_context():
            db.session.add(Setting(provider='ollama', base_url=None, model_name=None))
            db.session.commit()
            provider = get_llm_provider()

        assert isinstance(provider, OllamaProvider)
        assert provider.base_url == 'http://localhost:11434'
        assert provider.model_name == 'llama3.2:1b'

    def test_provider_requires_api_key_for_openai(self, client):
        """The OpenAI-compatible provider without a key must raise a clear error."""
        with client.application.app_context():
            provider = OpenAICompatibleProvider(
                'https://api.openai.com/v1', 'gpt-3.5-turbo', api_key=None
            )
            with pytest.raises(LLMProviderError):
                provider.generate('test')


class TestAdminLLMSettings:
    """Tests of the admin endpoints /api/admin/llm-settings."""

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

        # The configuration is persisted
        response2 = client.get('/api/admin/llm-settings', headers=auth_headers)
        assert response2.status_code == 200
        assert response2.get_json()['settings']['provider'] == 'ollama'

    def test_update_llm_settings_partial_switch(self, client, auth_headers):
        """Provider-only switch: the missing fields take the defaults of the
        target provider (ollama), not those of the previous provider (openai)."""
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
    """Tests of the edge/ollama warning on essay grading (paid feature)."""

    def test_evaluate_essay_falls_back_on_provider_error(self, client):
        """On provider error, fall back without crash and without edge warning."""

        class FailingProvider:
            name = 'openai'
            model_name = 'gpt-3.5-turbo'
            is_edge = False

            def generate(self, prompt, system=None, temperature=0.7, max_tokens=300):
                raise LLMProviderError('boom')

        with client.application.app_context():
            with patch('src.routes.learning.get_llm_provider', return_value=FailingProvider()):
                feedback, points, warning = evaluate_essay_with_ai('Q', 'R', 'E', 10)

        assert 'unavailable' in feedback
        assert points == 5  # default score (max_points // 2)
        assert warning is False

    def test_evaluate_essay_returns_edge_warning(self, client):
        """With an edge provider, the warning flag must be returned."""

        class EdgeProvider:
            name = 'ollama'
            model_name = 'llama3.2:1b'
            is_edge = True

            def generate(self, prompt, system=None, temperature=0.7, max_tokens=300):
                return 'Score: 8/10\nComments: Good work, keep it up.'

        with client.application.app_context():
            with patch('src.routes.learning.get_llm_provider', return_value=EdgeProvider()):
                feedback, points, warning = evaluate_essay_with_ai('Q', 'R', 'E', 10)

        assert points == 8
        assert 'Good work' in feedback
        assert warning is True

    def test_evaluate_essay_no_warning_for_cloud(self, client):
        """With a cloud provider, no edge warning."""

        class CloudProvider:
            name = 'openai'
            model_name = 'gpt-3.5-turbo'
            is_edge = False

            def generate(self, prompt, system=None, temperature=0.7, max_tokens=300):
                return 'Score: 9/10\nComments: Excellent.'

        with client.application.app_context():
            with patch('src.routes.learning.get_llm_provider', return_value=CloudProvider()):
                feedback, points, warning = evaluate_essay_with_ai('Q', 'R', 'E', 10)

        assert points == 9
        assert warning is False
