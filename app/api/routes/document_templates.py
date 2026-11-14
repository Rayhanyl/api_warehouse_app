"""Routes pengaturan template dokumen cetak modular dan logo perusahaan (Tahap 17 / Poin 10)."""

from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from psycopg import Connection

from app.api.deps import get_client_ip, get_current_user
from app.core.database import get_conn
from app.core.permissions import USER_MANAGE, require_permission
from app.schemas.document_template import (
    DocumentTemplateOut,
    DocumentTemplateUpdate,
    LogoUploadOut,
)
from app.services import document_template_service

router = APIRouter(prefix="/document-templates", tags=["Document Templates"])


@router.get("", response_model=list[DocumentTemplateOut])
def list_document_templates(
    _actor: dict[str, Any] = Depends(get_current_user),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> list[DocumentTemplateOut]:
    rows = document_template_service.list_templates(conn)
    return [DocumentTemplateOut(**row) for row in rows]


@router.post("/upload-logo", response_model=LogoUploadOut)
async def upload_document_logo(
    request: Request,
    file: UploadFile = File(...),
    actor: dict[str, Any] = Depends(require_permission(USER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> LogoUploadOut:
    result = await document_template_service.save_uploaded_logo(
        conn,
        file=file,
        actor=actor,
        ip_address=get_client_ip(request),
    )
    return LogoUploadOut(**result)


@router.get("/logos/{filename}")
def get_uploaded_logo(filename: str) -> FileResponse:
    file_path, media_type = document_template_service.resolve_logo_file_path(filename)
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.get("/{document_type}", response_model=DocumentTemplateOut)
def get_document_template(
    document_type: str,
    _actor: dict[str, Any] = Depends(get_current_user),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> DocumentTemplateOut:
    row = document_template_service.get_template(conn, document_type)
    return DocumentTemplateOut(**row)


@router.put("/{document_type}", response_model=DocumentTemplateOut)
def update_document_template(
    document_type: str,
    payload: DocumentTemplateUpdate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(USER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> DocumentTemplateOut:
    updated = document_template_service.update_template(
        conn,
        document_type=document_type,
        payload=payload,
        actor=actor,
        ip_address=get_client_ip(request),
    )
    return DocumentTemplateOut(**updated)
