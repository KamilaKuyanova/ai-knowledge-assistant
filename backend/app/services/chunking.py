"""Разбиение текста на фрагменты по границам абзацев и предложений, с перекрытием."""
import re
from dataclasses import dataclass

from app.services.parsing import ParsedPage

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")


@dataclass
class TextChunk:
    page: int | None
    text: str


def split_text(text: str, size: int, overlap: int) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n")).strip()
    units: list[str] = []
    for para in re.split(r"\n\s*\n|\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= size:
            units.append(para)
            continue
        for sentence in _SENTENCE_SPLIT.split(para):
            while len(sentence) > size:  # предложение длиннее лимита — режем жёстко
                units.append(sentence[:size])
                sentence = sentence[size:]
            if sentence:
                units.append(sentence)

    chunks: list[str] = []
    current = ""
    for unit in units:
        if current and len(current) + 1 + len(unit) > size:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            # перекрытие начинаем с границы слова, чтобы не рвать слова пополам
            tail = tail.split(" ", 1)[1] if " " in tail and len(current) > overlap else tail
            current = f"{tail} {unit}".strip() if tail else unit
        else:
            current = f"{current}\n{unit}" if current else unit
    if current:
        chunks.append(current)
    return chunks


def chunk_pages(pages: list[ParsedPage], size: int, overlap: int) -> list[TextChunk]:
    result: list[TextChunk] = []
    for page in pages:
        for piece in split_text(page.text, size, overlap):
            result.append(TextChunk(page=page.page, text=piece))
    return result
