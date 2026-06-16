import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, get_current_principal
from app.db.session import get_db_session
from app.models.document import Document
from app.schemas.document import DocumentRead
from app.services.ingestion.extractor import UnsupportedDocumentTypeError
from app.services.ingestion.pipeline import UPLOAD_DIR, IngestionPipeline

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 Mo


@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> Document:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Format non supporté. Formats acceptés : PDF, DOCX, TXT.",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"{principal.tenant_id}_{file.filename}"

    try:
        with dest.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        if dest.stat().st_size > MAX_FILE_SIZE:
            dest.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Fichier trop volumineux. Limite : 50 Mo.",
            )

        document = await IngestionPipeline(db).ingest_upload(
            file_path=dest,
            filename=file.filename or dest.name,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
        )
        return document

    except UnsupportedDocumentTypeError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    limit: int = Query(default=100, ge=1, le=500),
    include_deleted: bool = False,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> list[Document]:
    query = select(Document).where(Document.tenant_id == principal.tenant_id)
    if not include_deleted:
        query = query.where(Document.deleted_at.is_(None))
    result = await db.execute(
        query.order_by(Document.updated_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
