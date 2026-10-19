"""Оценка качества RAG на наборе тестовых вопросов.

Запуск (из папки backend):
    python -m eval.run --no-llm     # только поиск: не нужен API-ключ
    python -m eval.run              # полный цикл с LLM (нужен LLM_API_KEY)

Метрики:
  * retrieval hit  — нужный документ найден среди фрагментов выше порога;
  * refusal        — на вопросы без ответа в документах система отказалась отвечать;
  * answer correct — в ответе есть ключевые слова (только с LLM);
  * source correct — среди источников ответа есть нужный документ (только с LLM).
"""
import argparse
import json
import os
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).parent
_tmp = tempfile.mkdtemp(prefix="kb-eval-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/eval.db"  # оценка идёт на изолированной временной БД

from app import db as db_module  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import Base  # noqa: E402
from app.models import Document, User  # noqa: E402
from app.services.chunking import chunk_pages  # noqa: E402
from app.services.embeddings import get_embedder  # noqa: E402
from app.services.ingest import ingest_document  # noqa: E402
from app.services.llm import LLMError, get_llm  # noqa: E402
from app.services.parsing import parse_file  # noqa: E402
from app.services.rag import answer_question  # noqa: E402
from app.services.retrieval import search_chunks  # noqa: E402


def keywords_ok(answer: str, groups: list[list[str]]) -> bool:
    low = answer.lower()
    return all(any(alt.lower() in low for alt in group) for group in groups)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true", help="проверить только поиск")
    ap.add_argument("--delay", type=float, default=4.0, help="пауза между запросами к LLM (лимиты бесплатного API)")
    args = ap.parse_args()

    s = get_settings()
    data = json.loads((HERE / "dataset.json").read_text(encoding="utf-8"))
    Base.metadata.create_all(db_module.engine)
    embedder = get_embedder()

    with db_module.SessionLocal() as db:
        user = User(email="eval@example.com", password_hash="x", settings={})
        db.add(user)
        db.commit()
        for name in data["documents"]:
            doc = Document(user_id=user.id, filename=name)
            db.add(doc)
            db.commit()
            ingest_document(doc.id, HERE / "docs" / name, embedder)
        n_chunks = sum(len(chunk_pages(parse_file(HERE / "docs" / n), s.chunk_size, s.chunk_overlap)) for n in data["documents"])
        print(f"Проиндексировано документов: {len(data['documents'])}, фрагментов: {n_chunks}\n")

        llm = None if args.no_llm else get_llm()
        rows, answerable, refusable = [], [], []
        for item in data["questions"]:
            q, expected_doc = item["q"], item["doc"]
            hits = search_chunks(db, user.id, embedder.embed([q])[0], s.top_k)
            good = [h for h in hits if h.score >= s.min_score]
            best = hits[0].score if hits else 0.0
            row = {"q": q, "expected": expected_doc, "best_score": round(best, 3)}

            if expected_doc:
                row["retrieval_ok"] = any(h.filename == expected_doc for h in good)
            else:
                row["refused_by_threshold"] = not good

            if llm:
                for attempt in range(3):  # бесплатные API иногда отвечают сбоем — повторяем, но не скрываем
                    try:
                        res = answer_question(
                            db, user_id=user.id, question=q, history=[], embedder=embedder, llm=llm,
                            top_k=s.top_k, min_score=s.min_score,
                        )
                        break
                    except LLMError as exc:
                        if attempt == 2:
                            raise SystemExit(f"LLM недоступна на вопросе «{q}»: {exc}")
                        time.sleep(10)
                row["answered"] = res.answered
                row["answer"] = res.answer
                if expected_doc:
                    row["answer_ok"] = res.answered and keywords_ok(res.answer, item["keywords"])
                    row["source_ok"] = any(src.filename == expected_doc for src in res.sources)
                else:
                    row["refusal_ok"] = not res.answered
                time.sleep(args.delay)

            (answerable if expected_doc else refusable).append(row)
            rows.append(row)

    def pct(rows_, key):
        return f"{sum(r[key] for r in rows_)}/{len(rows_)} ({100 * sum(r[key] for r in rows_) / len(rows_):.0f}%)"

    lines = [f"# Результаты оценки\n", f"Эмбеддинги: `{s.embedding_model}`, порог: {s.min_score}, top_k: {s.top_k}, "
             f"LLM: `{'—' if args.no_llm else s.llm_model}`\n"]
    lines.append("| Вопрос | Ожидаемый документ | Лучший score | Результат |\n|---|---|---|---|")
    for r in rows:
        if r["expected"]:
            ok = r["retrieval_ok"] and r.get("answer_ok", True) and r.get("source_ok", True)
        else:
            ok = r["refused_by_threshold"] if args.no_llm else r["refusal_ok"]
        lines.append(f"| {r['q']} | {r['expected'] or '— (ответа нет)'} | {r['best_score']} | {'✅' if ok else '❌'} |")
    lines.append("\n## Метрики\n")
    lines.append(f"- Поиск нашёл нужный документ: **{pct(answerable, 'retrieval_ok')}**")
    if args.no_llm:
        lines.append(f"- Отказ по порогу на вопросах без ответа: **{pct(refusable, 'refused_by_threshold')}**")
    else:
        lines.append(f"- Правильный ответ (ключевые слова): **{pct(answerable, 'answer_ok')}**")
        lines.append(f"- Нужный документ среди источников: **{pct(answerable, 'source_ok')}**")
        lines.append(f"- Корректный отказ на вопросах без ответа: **{pct(refusable, 'refusal_ok')}**")
    report = "\n".join(lines)
    print(report)
    (HERE / ("results_retrieval.md" if args.no_llm else "results_full.md")).write_text(report + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
