import pytest

@pytest.fixture(autouse=True)
def isolate_model_credentials(monkeypatch):
    """Never spend real credentials loaded from a developer's local .env during tests."""
    for name in ('GROQ_API_KEY', 'GEMINI_API_KEY', 'GROQ_MODEL', 'GEMINI_MODEL', 'LLM_TIMEOUT_SECONDS'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('LLM_PROVIDER', 'auto')
    monkeypatch.setenv('LLM_FALLBACK_PROVIDER', 'offline')
