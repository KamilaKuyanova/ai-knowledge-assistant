from app.services.llm import ExtractiveStubLLM, LLMError, OpenAICompatibleLLM
from app.services.rag import build_messages
from app.services.retrieval import Hit

import pytest


def test_stub_answers_with_first_sentence_and_citation():
    hit = Hit(1, 1, "a.txt", None, "Заявление подаётся за 14 дней. Остальной текст.", 0.9)
    answer = ExtractiveStubLLM().complete(build_messages("Когда подать?", [hit], []))
    assert answer == "Заявление подаётся за 14 дней. [1]"


def test_stub_says_no_answer_without_context():
    assert ExtractiveStubLLM().complete([{"role": "user", "content": "ВОПРОС: ?"}]) == "NO_ANSWER"


def test_real_llm_without_key_gives_clear_error():
    llm = OpenAICompatibleLLM("http://localhost:1", "", "m", 0.1)
    with pytest.raises(LLMError, match="LLM_API_KEY"):
        llm.complete([{"role": "user", "content": "hi"}])
