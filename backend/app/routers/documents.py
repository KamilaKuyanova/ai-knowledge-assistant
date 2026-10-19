import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Document, User
from app.schemas import DocumentOut
from app.security import get_current_user
from app.services.embeddings import Embedder, get_embedder
from app.services.ingest import ingest_document
from app.services.parsing import SUPPORTED_EXTENSIONS

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _get_own(db: Session, user: User, document_id: int) -> Document:
    doc = db.get(Document, document_id)
    if doc is None or doc.user_id != user.id:  # чужой документ неотличим от несуществующего
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Документ не найден")
    return doc


def _stored_path(user_id: int, document_id: int, filename: str) -> Path:
    return Path(get_settings().upload_dir) / str(user_id) / f"{document_id}{Path(filename).suffix.lower()}"


@router.get("", response_model=list[DocumentOut])
def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Document).where(Document.user_id == user.id).order_by(Document.id.desc())).all()


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_own(db, user, document_id)


@router.post("", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
):
    s = get_settings()
    filename = Path(file.filename or "document").name  # отбрасываем любые пути из имени
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Поддерживаются только PDF, DOCX и TXT")

    data = await file.read(s.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Файл больше {s.max_upload_mb} МБ")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Файл пустой")

    doc = Document(user_id=user.id, filename=filename, status="processing")
    db.add(doc)
    db.commit()

    path = _stored_path(user.id, doc.id, filename)  # на диске имя не зависит от пользовательского ввода
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    background.add_task(ingest_document, doc.id, path, embedder)
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _get_own(db, user, document_id)
    path = _stored_path(user.id, doc.id, doc.filename)
    db.delete(doc)
    db.commit()
    path.unlink(missing_ok=True)
