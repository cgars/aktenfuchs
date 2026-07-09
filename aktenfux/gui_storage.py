"""Filesystem-backed storage for GUI review documents.

Documents are read from and written back to the aktenfux pipeline's ``_Review``
directory, using the standard :class:`~aktenfux.schema.SidecarDocument` JSON
format.  GUI-specific state (notes, tasks, split markers, review state, …) that
has no counterpart in the pipeline schema is persisted in a lightweight
``<stem>.gui.json`` overlay file stored alongside the pipeline sidecar.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from aktenfux.config import AktenfuxConfig
from aktenfux.gui_models import (
    DocumentQueueItem,
    GuiOverlay,
    ReviewDocument,
    review_document_to_overlay,
    sidecar_to_review_document,
)
from aktenfux.review import find_document_by_id
from aktenfux.schema import DESCRIPTION_SHORT_MAX_CHARS, SidecarDocument
from aktenfux.storage import read_sidecar, write_sidecar

_OVERLAY_SUFFIX = ".gui.json"


def _overlay_path_for(pdf_path: Path) -> Path:
    return pdf_path.parent / (pdf_path.stem + _OVERLAY_SUFFIX)


def _read_overlay(pdf_path: Path) -> GuiOverlay:
    path = _overlay_path_for(pdf_path)
    if path.exists():
        try:
            return GuiOverlay.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return GuiOverlay()


def _write_overlay(pdf_path: Path, overlay: GuiOverlay) -> None:
    path = _overlay_path_for(pdf_path)
    path.write_text(overlay.model_dump_json(indent=2), encoding="utf-8")


def _update_sidecar_from_gui(sidecar: SidecarDocument, doc: ReviewDocument) -> SidecarDocument:
    """Return a copy of *sidecar* updated with user-edited fields from *doc*.

    Only fields that have a meaningful pipeline counterpart are copied; GUI-only
    fields (notes, tasks, overlay metadata, …) are intentionally ignored here
    and persisted separately in the :func:`_write_overlay` call.
    """
    data: dict[str, Any] = sidecar.model_dump()

    data["summary"] = doc.description.summary
    if doc.description.summary:
        data["summary_short"] = doc.description.summary[:DESCRIPTION_SHORT_MAX_CHARS].rstrip()

    # document_type: the schema validator handles German aliases → canonical type.
    dt_val = doc.metadata.document_type.value
    data["document_type"] = str(dt_val) if dt_val else "Other"

    date_val = doc.metadata.date.value
    data["document_date"] = str(date_val) if date_val else None

    correspondent_val = doc.metadata.sender.value
    data["correspondent"] = str(correspondent_val) if correspondent_val else None

    data["topic"] = str(doc.metadata.subject.value) if doc.metadata.subject.value else ""

    deadline_val = doc.metadata.deadline.value
    data["deadline"] = str(deadline_val) if deadline_val else None

    data["entities"]["people"] = list(doc.metadata.persons)
    data["entities"]["organizations"] = list(doc.metadata.organizations)
    data["tags"] = list(doc.metadata.tags)

    archive_path = doc.metadata.suggested_archive_path
    if "/" in archive_path:
        idx = archive_path.rfind("/")
        data["suggested_folder"] = archive_path[:idx]
        data["suggested_filename"] = archive_path[idx + 1:]
    elif archive_path:
        data["suggested_filename"] = archive_path

    return SidecarDocument.model_validate(data)


class GuiDocumentStore:
    """Reads and writes pipeline documents for the review GUI.

    *review_path* is the directory scanned for ``*.pdf`` files (and their
    companion ``*.json`` sidecars).  In production this is
    ``config.review_path``; in the fallback / test mode it points at the
    ``mock_data/_Review`` directory shipped with the package.

    *config* is optional.  When provided, approval and re-processing calls are
    forwarded to the actual pipeline functions.  Without it, only the local
    overlay file is updated (mock / test mode).
    """

    def __init__(
        self,
        review_path: Path,
        base_dir: Path,
        config: AktenfuxConfig | None = None,
    ) -> None:
        self.review_path = review_path
        self.base_dir = base_dir
        self.config = config
        review_path.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_documents(self) -> list[DocumentQueueItem]:
        items: list[DocumentQueueItem] = []
        for pdf in sorted(self.review_path.glob("*.pdf")):
            sidecar = read_sidecar(pdf)
            if sidecar is None:
                continue
            overlay = _read_overlay(pdf)
            items.append(DocumentQueueItem(
                id=sidecar.id,
                source_file=Path(sidecar.original_path).name,
                status=overlay.gui_status,
            ))
        return items

    def get_document(self, doc_id: str) -> ReviewDocument:
        pdf_path, sidecar = self._require(doc_id)
        overlay = _read_overlay(pdf_path)
        return sidecar_to_review_document(sidecar, pdf_path, overlay)

    def save_document(self, doc_id: str, document: ReviewDocument) -> ReviewDocument:
        if doc_id != document.id:
            raise HTTPException(status_code=400, detail="Document ID mismatch")
        pdf_path, sidecar = self._require(doc_id)
        updated_sidecar = _update_sidecar_from_gui(sidecar, document)
        write_sidecar(updated_sidecar, pdf_path)
        overlay = review_document_to_overlay(document)
        _write_overlay(pdf_path, overlay)
        return sidecar_to_review_document(updated_sidecar, pdf_path, overlay)

    def approve_document(self, doc_id: str) -> ReviewDocument:
        pdf_path, sidecar = self._require(doc_id)
        overlay = _read_overlay(pdf_path)
        reviewed_at = datetime.now().isoformat(timespec="seconds")

        if self.config is not None:
            from aktenfux.main import approve_document as _pipeline_approve  # noqa: PLC0415
            _pipeline_approve(doc_id, self.config)
            # The PDF + sidecar have been moved out of _Review by the pipeline.
            # Return the pre-move document data with the updated status.
        else:
            # Mock / no-config mode: persist via overlay only.
            overlay.reviewed = True
            overlay.reviewed_at = reviewed_at
            overlay.gui_status = "approved"
            _write_overlay(pdf_path, overlay)

        doc = sidecar_to_review_document(sidecar, pdf_path, overlay)
        doc.status = "approved"
        doc.metadata.status = "approved"
        doc.review.reviewed = True
        doc.review.reviewed_at = reviewed_at
        return doc

    def mark_needs_split_review(self, doc_id: str) -> ReviewDocument:
        pdf_path, _ = self._require(doc_id)
        overlay = _read_overlay(pdf_path)
        overlay.gui_status = "needs_split_review"
        _write_overlay(pdf_path, overlay)
        return self.get_document(doc_id)

    def split_document(self, doc_id: str) -> dict:
        """Split the document at its saved split markers.

        Splits are written to *_Inbox* as individual PDFs; the original
        PDF, sidecar, and GUI overlay are moved to *_SplittedDocs*.
        Returns a status dict with the names of the files created in Inbox.
        In mock/test mode (no config) a descriptive no-op response is returned.
        """
        pdf_path, _ = self._require(doc_id)
        overlay = _read_overlay(pdf_path)
        markers = list(overlay.split_markers)

        if not markers:
            raise HTTPException(
                status_code=400,
                detail="No split markers set. Use 'Set split marker' (T) to mark pages first.",
            )

        if self.config is None:
            return {
                "status": "not_implemented",
                "message": "Split pipeline not available in test mode (no config.yaml found).",
                "created_files": [],
            }

        from aktenfux.main import split_document as _pipeline_split  # noqa: PLC0415

        created = _pipeline_split(doc_id, markers, self.config)
        return {
            "status": "ok",
            "message": f"Document split into {len(created)} part(s) and moved to Inbox.",
            "created_files": created,
        }

    def resolve_pdf_path(self, doc: ReviewDocument) -> Path:
        raw_path = Path(doc.pdf_path)
        candidate = raw_path if raw_path.is_absolute() else self.base_dir / raw_path
        resolved = candidate.resolve()
        if not resolved.exists():
            raise HTTPException(
                status_code=404,
                detail=f"PDF not found for document '{doc.id}'",
            )
        return resolved

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require(self, doc_id: str) -> tuple[Path, SidecarDocument]:
        result = find_document_by_id(self.review_path, doc_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
        return result
