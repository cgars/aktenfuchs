"""Filesystem-backed storage for GUI review documents."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import HTTPException

from aktenfux.gui_models import DocumentQueueItem, ReviewDocument


class GuiDocumentStore:
    def __init__(self, data_dir: Path, base_dir: Path) -> None:
        self.data_dir = data_dir
        self.base_dir = base_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _document_file(self, doc_id: str) -> Path:
        return self.data_dir / f"{doc_id}.json"

    def list_documents(self) -> list[DocumentQueueItem]:
        items: list[DocumentQueueItem] = []
        for path in sorted(self.data_dir.glob("*.json")):
            doc = ReviewDocument.model_validate_json(path.read_text(encoding="utf-8"))
            items.append(DocumentQueueItem(id=doc.id, source_file=doc.source_file, status=doc.status))
        return items

    def get_document(self, doc_id: str) -> ReviewDocument:
        path = self._document_file(doc_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
        return ReviewDocument.model_validate_json(path.read_text(encoding="utf-8"))

    def save_document(self, doc_id: str, document: ReviewDocument) -> ReviewDocument:
        if doc_id != document.id:
            raise HTTPException(status_code=400, detail="Document ID mismatch")
        path = self._document_file(doc_id)
        path.write_text(document.model_dump_json(indent=2), encoding="utf-8")
        return document

    def approve_document(self, doc_id: str) -> ReviewDocument:
        doc = self.get_document(doc_id)
        doc.status = "approved"
        doc.metadata.status = "approved"
        doc.review.reviewed = True
        doc.review.reviewed_at = datetime.now().isoformat(timespec="seconds")
        return self.save_document(doc_id, doc)

    def mark_needs_split_review(self, doc_id: str) -> ReviewDocument:
        doc = self.get_document(doc_id)
        doc.status = "needs_split_review"
        doc.metadata.status = "needs_split_review"
        return self.save_document(doc_id, doc)

    def resolve_pdf_path(self, doc: ReviewDocument) -> Path:
        raw_path = Path(doc.pdf_path)
        candidate = raw_path if raw_path.is_absolute() else self.base_dir / raw_path
        resolved = candidate.resolve()
        if not resolved.exists():
            raise HTTPException(status_code=404, detail=f"PDF not found for document '{doc.id}'")
        return resolved


