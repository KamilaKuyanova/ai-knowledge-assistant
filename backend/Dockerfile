FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 FASTEMBED_CACHE_PATH=/opt/fastembed

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Модель эмбеддингов скачиваем при сборке, чтобы первый запуск не ждал загрузки.
ARG EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('${EMBEDDING_MODEL}')"

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
