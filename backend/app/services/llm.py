"""Тонкая обёртка над OpenAI-совместимым chat API. Меняя LLM_BASE_URL / LLM_MODEL, можно
переключаться между Gemini, Groq, OpenRouter, Ollama и самим OpenAI без правок кода."""
from functools import lru_cache
from typing import Protocol

from app.config import get_settings


class LLMError(Exception):
    """Ошибка обращения к LLM; message безопасно показывать пользователю."""


class LLM(Protocol):
    def complete(self, messages: list[dict]) -> str: ...


class OpenAICompatibleLLM:
    def __init__(self, base_url: str, api_key: str, model: str, temperature: float):
        from openai import OpenAI

        self._client = OpenAI(base_url=base_url, api_key=api_key or "missing", max_retries=2, timeout=30)
        self._model = model
        self._temperature = temperature
        self._has_key = bool(api_key)

    def complete(self, messages: list[dict]) -> str:
        import openai

        if not self._has_key:
            raise LLMError("Не задан LLM_API_KEY. Получите бесплатный ключ и добавьте его в .env (см. README).")
        try:
            resp = self._client.chat.completions.create(
                model=self._model, messages=messages, temperature=self._temperature
            )
        except openai.RateLimitError as exc:
            raise LLMError("Превышен лимит бесплатного API. Подождите минуту и повторите запрос.") from exc
        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            raise LLMError("API-ключ отклонён. Проверьте LLM_API_KEY.") from exc
        except openai.NotFoundError as exc:
            raise LLMError(f"Модель «{self._model}» недоступна. Проверьте LLM_MODEL.") from exc
        except (openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError) as exc:
            raise LLMError("Модель не ответила вовремя. Повторите запрос через несколько секунд.") from exc
        except openai.APIError as exc:
            raise LLMError(f"Ошибка LLM-провайдера: {exc.__class__.__name__}") from exc
        return (resp.choices[0].message.content or "").strip()


class ExtractiveStubLLM:
    """Заглушка: отвечает первым предложением самого релевантного фрагмента со ссылкой [1].
    Качество настоящей модели не отражает."""

    def complete(self, messages: list[dict]) -> str:
        import re

        context = messages[-1]["content"]
        m = re.search(r"\[1\] \([^)]*\)\n(.+?)(?:\n\n|\nВОПРОС:)", context, re.S)
        first = re.split(r"(?<=[.!?])\s+", " ".join(m.group(1).split()))[0] if m else ""
        return f"{first} [1]" if first else "NO_ANSWER"


@lru_cache
def get_llm() -> LLM:
    s = get_settings()
    if s.llm_provider == "stub":
        return ExtractiveStubLLM()
    return OpenAICompatibleLLM(s.llm_base_url, s.llm_api_key, s.llm_model, s.llm_temperature)
