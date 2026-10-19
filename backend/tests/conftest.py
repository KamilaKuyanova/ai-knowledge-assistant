import hashlib
import math
import os
import re
import tempfile

# Настройки нужно задать ДО импорта приложения.
_tmp = tempfile.mkdtemp(prefix="kb-tests-")
os.environ.update(
    DATABASE_URL=f"sqlite:///{_tmp}/test.db",
    UPLOAD_DIR=f"{_tmp}/uploads",
    EMBEDDING_DIM="128",
    JWT_SECRET="test-secret-test-secret-test-secret-0123",
    MIN_SCORE="0.2",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.embeddings import get_embedder  # noqa: E402
from app.services.llm import get_llm  # noqa: E402


class FakeEmbedder:
    """Детерминированные «эмбеддинги»: хэшированный мешок слов. Тексты с общими словами близки."""

    DIM = 128

    def embed(self, texts):
        out = []
        for t in texts:
            v = [0.0] * self.DIM
            for w in re.findall(r"\w+", t.lower()):
                if len(w) > 3:
                    v[int(hashlib.md5(w[:5].encode()).hexdigest(), 16) % self.DIM] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm for x in v])
        return out


class FakeLLM:
    """Записывает вызовы; отвечает цитатой первого фрагмента, либо NO_ANSWER по настройке."""

    def __init__(self):
        self.calls = []
        self.reply = None

    def complete(self, messages):
        self.calls.append(messages)
        return self.reply if self.reply is not None else "Ответ по документу [1]."


@pytest.fixture(autouse=True)
def _db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def client(llm):
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    app.dependency_overrides[get_llm] = lambda: llm
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register(client, email="a@example.com", password="password123"):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client):
    return register(client)
