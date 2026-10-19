from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/knowledge"

    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 60 * 24 * 7

    # LLM: любой OpenAI-совместимый эндпоинт (Gemini, Groq, OpenRouter, Ollama, OpenAI).
    # "openai" — настоящая модель; "stub" — заглушка без сети и ключа (отвечает первым предложением
    # найденного фрагмента), для разработки интерфейса и демо без расхода лимитов.
    llm_provider: str = "openai"
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_api_key: str = ""
    llm_model: str = "gemini-3.5-flash"
    llm_temperature: float = 0.1

    # Эмбеддинги: "local" (fastembed, без ключа и лимитов) или "api" (OpenAI-совместимый /embeddings).
    embeddings_provider: str = "local"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384
    embeddings_base_url: str = ""  # по умолчанию = llm_base_url
    embeddings_api_key: str = ""  # по умолчанию = llm_api_key

    upload_dir: str = "./uploads"
    max_upload_mb: int = 20

    chunk_size: int = 1000
    chunk_overlap: int = 150

    # Поиск: сколько фрагментов брать и минимальная косинусная близость, ниже которой
    # система отказывается отвечать, не обращаясь к LLM.
    top_k: int = 5
    min_score: float = 0.35
    history_messages: int = 6

    cors_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
