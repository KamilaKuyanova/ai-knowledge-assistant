"""Обработка загруженного файла: текст -> фрагменты -> эмбеддинги -> БД."""
import logging
from pathlib import Path

from app import db as db_module
from app.config import get_settings
from app.models import Chunk, Document
from app.services.chunking import chunk_pages
from app.services.embeddings import Embedder
from app.services.parsing import ParsingError, parse_file

log = logging.getLogger(__name__)
EMBED_BATCH = 32


def ingest_document(document_id: int, path: Path, embedder: Embedder) -> None:
    """Запускается в фоне после ответа на загрузку; статус документа отражает результат."""
    s = get_settings()
    with db_module.SessionLocal() as db:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        try:
            pages = parse_file(path)
            chunks = chunk_pages(pages, s.chunk_size, s.chunk_overlap)
            vectors: list[list[float]] = []
            for i in range(0, len(chunks), EMBED_BATCH):
                vectors.extend(embedder.embed([c.text for c in chunks[i : i + EMBED_BATCH]]))
            db.add_all(
                Chunk(document_id=doc.id, user_id=doc.user_id, position=i, page=c.page, text=c.text, embedding=v)
                for i, (c, v) in enumerate(zip(chunks, vectors))
            )
            doc.page_count = len([p for p in pages if p.page is not None]) or None
            doc.chunk_count = len(chunks)
            doc.status = "ready"
        except ParsingError as exc:
            doc.status, doc.error = "failed", str(exc)
        except Exception:
            log.exception("Ошибка индексации документа %s", document_id)
            doc.status, doc.error = "failed", "Внутренняя ошибка при индексации. Попробуйте загрузить файл ещё раз."
        db.commit()
