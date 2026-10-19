from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Conversation, Message, User
from app.schemas import AskIn, ConversationOut, MessageOut, UserSettings
from app.security import get_current_user
from app.services.embeddings import Embedder, get_embedder
from app.services.llm import LLM, LLMError, get_llm
from app.services.rag import answer_question

router = APIRouter(prefix="/api/chats", tags=["chats"])


def _get_own(db: Session, user: User, chat_id: int) -> Conversation:
    chat = db.get(Conversation, chat_id)
    if chat is None or chat.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Чат не найден")
    return chat


@router.get("", response_model=list[ConversationOut])
def list_chats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.id.desc())).all()


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_chat(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chat = Conversation(user_id=user.id)
    db.add(chat)
    db.commit()
    return chat


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
def list_messages(chat_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_own(db, user, chat_id).messages


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(chat_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_get_own(db, user, chat_id))
    db.commit()


@router.post("/{chat_id}/ask", response_model=MessageOut)
def ask(
    chat_id: int,
    data: AskIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    llm: LLM = Depends(get_llm),
):
    s = get_settings()
    chat = _get_own(db, user, chat_id)
    prefs = UserSettings(**{"top_k": s.top_k, "min_score": s.min_score, **(user.settings or {})})

    # В историю для модели идут только реальные ответы — отказы только запутывают.
    history = [
        {"role": m.role, "content": m.content}
        for m in chat.messages[-s.history_messages :]
        if m.role == "user" or m.answered
    ]

    try:
        result = answer_question(
            db,
            user_id=user.id,
            question=data.question,
            history=history,
            embedder=embedder,
            llm=llm,
            top_k=prefs.top_k,
            min_score=prefs.min_score,
        )
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))

    if not chat.messages:
        chat.title = data.question[:60]
    db.add(Message(conversation_id=chat.id, role="user", content=data.question))
    reply = Message(
        conversation_id=chat.id,
        role="assistant",
        content=result.answer,
        sources=[src.as_dict() for src in result.sources],
        answered=result.answered,
    )
    db.add(reply)
    db.commit()
    return reply
