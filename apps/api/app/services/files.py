import uuid
from pathlib import Path

from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import get_settings, repo_root
from app.errors import DomainError
from app.models import Product, ProductDocument, User
from app.services.common import require

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "text/plain": ".txt",
}


def upload_root() -> Path:
    configured = Path(get_settings().upload_dir)
    root = configured if configured.is_absolute() else repo_root() / "apps" / "api" / configured
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def save_document(session: Session, actor: User, product_id, filename: str, content_type: str, payload: bytes) -> ProductDocument:
    product = require(session, Product, product_id, "Product")
    extension = ALLOWED_TYPES.get(content_type)
    if extension is None:
        raise DomainError(422, "invalid_file", "Allowed file types are PDF, PNG, JPEG, and plain text.")
    if not payload or len(payload) > 5_000_000:
        raise DomainError(422, "invalid_file", "File must be between 1 byte and 5 MB.")
    stored = f"{uuid.uuid4()}{extension}"
    destination = upload_root() / stored
    destination.write_bytes(payload)
    row = ProductDocument(
        product_id=product.id,
        doc_type=extension.lstrip("."),
        storage_path=stored,
        filename=Path(filename).name[:200] or stored,
        content_type=content_type,
        byte_size=len(payload),
    )
    session.add(row)
    session.flush()
    audit(session, actor, "document.uploaded", "product_document", row.id, {"product_id": str(product.id)})
    return row


def open_document(session: Session, document_id) -> FileResponse:
    row = require(session, ProductDocument, document_id, "Document")
    root = upload_root()
    path = (root / row.storage_path).resolve()
    if root not in path.parents or not path.is_file():
        raise DomainError(404, "not_found", "Document file is missing.")
    return FileResponse(path, media_type=row.content_type, filename=row.filename)
