"""Локальный запуск БЕЗ Docker, PostgreSQL и API-ключа — только для разработки интерфейса.

SQLite вместо PostgreSQL, настоящие локальные эмбеддинги, а вместо LLM — заглушка, которая отвечает
первым предложением самого релевантного фрагмента со ссылкой [1]. Качество ответов это НЕ отражает.

    python -m scripts.dev_server        # из папки backend, API на http://localhost:8000
"""
import os
import tempfile
from pathlib import Path

_dir = Path(tempfile.gettempdir()) / "kb-dev"
_dir.mkdir(exist_ok=True)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_dir / 'dev.db'}")
os.environ.setdefault("UPLOAD_DIR", str(_dir / "uploads"))

import uvicorn  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.llm import ExtractiveStubLLM, get_llm  # noqa: E402


Base.metadata.create_all(engine)
app.dependency_overrides[get_llm] = lambda: ExtractiveStubLLM()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
