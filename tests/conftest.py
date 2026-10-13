"""
Shared test setup: fake credentials so the app imports without touching real
services, and the repo root as CWD so StaticFiles/templates resolve.
"""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
# supabase-py only checks that keys look like JWTs; these are not real credentials
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoidGVzdCJ9.dGVzdA"
os.environ.setdefault("SUPABASE_ANON_KEY", FAKE_JWT)
os.environ.setdefault("SUPABASE_SERVICE_KEY", FAKE_JWT)
os.environ.pop("ENVIRONMENT", None)

os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def api():
    import ai_search_api
    ai_search_api._cache.clear()
    ai_search_api.auth_rate_limit_store.clear()
    ai_search_api.login_failure_store.clear()
    ai_search_api.rate_limit_store.clear()
    return ai_search_api


@pytest.fixture
def client(api):
    from fastapi.testclient import TestClient
    return TestClient(api.app)
