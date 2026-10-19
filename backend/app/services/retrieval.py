"""Векторный поиск фрагментов. Всегда фильтрует по владельцу — чужие документы недоступны."""
import math
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Chunk, Document


@dataclass
class Hit:
    chunk_id: int
    document_id: int
    filename: str
    page: int | None
    text: str
    score: float  # косинусная близость, 1.0 — идентичные по смыслу


def search_chunks(db: Session, user_id: int, query_vec: list[float], top_k: int) -> list[Hit]:
    if db.get_bind().dialect.name == "postgresql":
        return _search_pgvector(db, user_id, query_vec, top_k)
    return _search_python(db, user_id, query_vec, top_k)


def _search_pgvector(db: Session, user_id: int, query_vec: list[float], top_k: int) -> list[Hit]:
    vec = "[" + ",".join(f"{x:.6f}" for x in query_vec) + "]"
    rows = db.execute(
        text(
            """
            SELECT c.id, c.document_id, d.filename, c.page, c.text,
                   1 - (c.embedding <=> CAST(:q AS vector)) AS score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.user_id = :uid AND d.status = 'ready'
            ORDER BY c.embedding <=> CAST(:q AS vector)
            LIMIT :k
            """
        ),
        {"q": vec, "uid": user_id, "k": top_k},
    ).all()
    return [Hit(r.id, r.document_id, r.filename, r.page, r.text, float(r.score)) for r in rows]


def _search_python(db: Session, user_id: int, query_vec: list[float], top_k: int) -> list[Hit]:
    """Запасной путь для SQLite (тесты): косинус считаем в Python, вектора уже нормализованы."""
    rows = db.execute(
        select(Chunk, Document.filename)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.user_id == user_id, Document.status == "ready")
    ).all()
    hits = [
        Hit(c.id, c.document_id, filename, c.page, c.text, sum(a * b for a, b in zip(c.embedding, query_vec)))
        for c, filename in rows
    ]
    hits.sort(key=lambda h: h.score, reverse=True)
    return [h for h in hits[:top_k] if not math.isnan(h.score)]
