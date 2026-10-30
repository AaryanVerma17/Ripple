import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
for k in ("NEBIUS_API_KEY", "NEBIUS_BASE_URL", "NEBIUS_MODEL", "GEMINI_API_KEY"):
    os.environ[k] = ""

import pytest  # noqa: E402

from app import llm, store  # noqa: E402
from app.config import settings  # noqa: E402


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    store.clear_overrides()
    monkeypatch.setattr(llm, "_transport", None)
    for k, v in dict(nebius_api_key="", nebius_base_url="", nebius_model="", gemini_api_key="", vision_provider="auto").items():
        monkeypatch.setattr(settings, k, v)
    yield
    store.clear_overrides()
