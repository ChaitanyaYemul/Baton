import pytest
import os
from pathlib import Path

def pytest_configure(config):
    if config.option.basetemp is None:
        root=Path(config.rootpath).resolve()
        target=(root/'tmp'/('pytest-'+str(os.getpid()))).resolve()
        if not target.is_relative_to(root):raise RuntimeError('Test directory must stay inside the workspace')
        target.parent.mkdir(parents=True,exist_ok=True)
        config.option.basetemp=str(target)

@pytest.fixture(autouse=True)
def isolate_model_credentials(monkeypatch):
    """Never spend real credentials loaded from a developer's local .env during tests."""
    for name in ('GROQ_API_KEY', 'GEMINI_API_KEY', 'GROQ_MODEL', 'GEMINI_MODEL', 'LLM_TIMEOUT_SECONDS','DATABASE_URL'):
        monkeypatch.delenv(name, raising=False)
    for role in ('REVIEWER','SUCCESSOR','COORDINATOR','LEAVER'):
        monkeypatch.delenv('BATON_'+role+'_PASSWORD',raising=False)
    monkeypatch.setenv('LLM_PROVIDER', 'auto')
    monkeypatch.setenv('LLM_FALLBACK_PROVIDER', 'offline')
