from app.services.rag import QUOTE_MAX_CHARS, best_quote, cited_hits
from app.services.retrieval import Hit


def make_hit(i):
    return Hit(chunk_id=i, document_id=i, filename=f"d{i}.txt", page=None, text="t", score=0.9)


def test_short_chunk_is_quoted_whole():
    assert best_quote("Короткий  текст.", "вопрос", "ответ") == "Короткий текст."


def test_long_chunk_quote_centers_on_relevant_sentence():
    filler = "Общие положения не относятся к вопросу и занимают много места. " * 8
    chunk = filler + "Заявление подаётся не позднее чем за 14 календарных дней. " + filler
    quote = best_quote(chunk, "За сколько дней подать заявление?", "Не позднее чем за 14 дней [1].")
    assert "14 календарных дней" in quote
    assert len(quote) <= QUOTE_MAX_CHARS


def test_only_cited_fragments_become_sources():
    hits = [make_hit(1), make_hit(2), make_hit(3)]
    assert cited_hits("Ответ [3] и ещё [3][1].", hits) == [hits[2], hits[0]]


def test_no_or_invalid_citations_fall_back_to_all_hits():
    hits = [make_hit(1), make_hit(2)]
    assert cited_hits("Ответ без ссылок", hits) == hits
    assert cited_hits("Ссылка на несуществующий [9]", hits) == hits
