"""Pydantic models for the Aktenfux review GUI MVP."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from aktenfux.schema import SidecarDocument

DocumentQueueStatus = Literal[
    "imported",
    "ocr_done",
    "ai_described",
    "needs_review",
    "needs_split_review",
    "metadata_review",
    "approved",
    "archived",
]

MetadataValueState = Literal["empty", "suggested", "confirmed"]


class MetadataValue(BaseModel):
    value: str | float | None = None
    state: MetadataValueState = "empty"
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class TaskItem(BaseModel):
    label: str
    done: bool = False


class DescriptionBlock(BaseModel):
    summary: str = ""
    markdown: str = ""
    ocr_text: str = ""
    notes: str = ""
    tasks: list[TaskItem] = Field(default_factory=list)


class MetadataBlock(BaseModel):
    document_type: MetadataValue = Field(default_factory=MetadataValue)
    date: MetadataValue = Field(default_factory=MetadataValue)
    sender: MetadataValue = Field(default_factory=MetadataValue)
    recipient: MetadataValue = Field(default_factory=MetadataValue)
    subject: MetadataValue = Field(default_factory=MetadataValue)
    reference: MetadataValue = Field(default_factory=MetadataValue)
    amount: MetadataValue = Field(default_factory=MetadataValue)
    deadline: MetadataValue = Field(default_factory=MetadataValue)
    location: MetadataValue = Field(default_factory=MetadataValue)
    persons: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    confidentiality: str = "private"
    suggested_archive_path: str = ""
    status: DocumentQueueStatus = "needs_review"


class ReviewState(BaseModel):
    reviewed: bool = False
    reviewed_at: str | None = None


class GuiOverlay(BaseModel):
    """GUI-specific state stored alongside each pipeline sidecar (.gui.json)."""

    # Description extras (not in pipeline sidecar)
    notes: str = ""
    tasks: list[TaskItem] = Field(default_factory=list)
    ocr_text: str = ""
    markdown: str = ""
    # Document processing
    split_markers: list[int] = Field(default_factory=list)
    # Review state
    reviewed: bool = False
    reviewed_at: str | None = None
    gui_status: DocumentQueueStatus = "needs_review"
    # Metadata fields without direct pipeline equivalents
    recipient: str = ""
    reference: str = ""
    location: str = ""
    amount: str = ""
    confidentiality: str = "private"


class ReviewDocument(BaseModel):
    id: str
    source_file: str
    pdf_path: str
    pages: list[int] = Field(default_factory=list)
    status: DocumentQueueStatus = "needs_review"
    split_markers: list[int] = Field(default_factory=list)
    description: DescriptionBlock = Field(default_factory=DescriptionBlock)
    metadata: MetadataBlock = Field(default_factory=MetadataBlock)
    review: ReviewState = Field(default_factory=ReviewState)


class DocumentQueueItem(BaseModel):
    id: str
    source_file: str
    status: DocumentQueueStatus


DOCUMENT_TYPE_OPTIONS = [
    "Invoice",
    "Contract",
    "Notice",
    "Policy",
    "BankStatement",
    "Letter",
    "Receipt",
    "Manual",
    "Other",
]


# ---------------------------------------------------------------------------
# Conversion helpers between SidecarDocument and ReviewDocument
# ---------------------------------------------------------------------------


def sidecar_to_review_document(
    sidecar: "SidecarDocument",
    pdf_path: Path,
    overlay: GuiOverlay,
) -> ReviewDocument:
    """Build a :class:`ReviewDocument` from a pipeline sidecar + GUI overlay."""
    from aktenfux.schema import SidecarDocument  # noqa: F401 – used by type checker only

    # Derive GUI status: use overlay if the user set a sub-status, but always
    # honour a pipeline-level "approved" so it isn't shadowed by the default.
    gui_status = overlay.gui_status
    if gui_status == "needs_review" and sidecar.status == "approved":
        gui_status = "approved"

    # First amount from sidecar amounts, or user-edited overlay value.
    amount_str = overlay.amount
    if not amount_str and sidecar.amounts:
        amount_str = str(sidecar.amounts[0].amount)

    # Combine suggested_folder + suggested_filename into a single archive path.
    if sidecar.suggested_folder and sidecar.suggested_filename:
        archive_path = f"{sidecar.suggested_folder}/{sidecar.suggested_filename}"
    else:
        archive_path = sidecar.suggested_filename or sidecar.suggested_folder or ""

    def _meta(value: object, *, confidence: float | None = None) -> MetadataValue:
        if value is None or value == "":
            return MetadataValue(state="empty")
        return MetadataValue(value=str(value), state="suggested", confidence=confidence)

    doc_type_confidence = sidecar.confidence if sidecar.confidence > 0 else None

    return ReviewDocument(
        id=sidecar.id,
        source_file=Path(sidecar.original_path).name,
        pdf_path=str(pdf_path.resolve()),
        status=gui_status,
        split_markers=list(overlay.split_markers),
        description=DescriptionBlock(
            summary=sidecar.summary,
            markdown=overlay.markdown or sidecar.summary,
            ocr_text=overlay.ocr_text,
            notes=overlay.notes,
            tasks=list(overlay.tasks),
        ),
        metadata=MetadataBlock(
            document_type=MetadataValue(
                value=sidecar.document_type,
                state="suggested",
                confidence=doc_type_confidence,
            ),
            date=_meta(sidecar.document_date),
            sender=_meta(sidecar.correspondent),
            recipient=_meta(overlay.recipient),
            subject=_meta(sidecar.topic),
            reference=_meta(overlay.reference),
            amount=_meta(amount_str),
            deadline=_meta(sidecar.deadline),
            location=_meta(overlay.location),
            persons=list(sidecar.entities.people),
            organizations=list(sidecar.entities.organizations),
            tags=list(sidecar.tags),
            confidentiality=overlay.confidentiality,
            suggested_archive_path=archive_path,
            status=gui_status,
        ),
        review=ReviewState(
            reviewed=overlay.reviewed,
            reviewed_at=overlay.reviewed_at,
        ),
    )


def review_document_to_overlay(doc: ReviewDocument) -> GuiOverlay:
    """Capture all GUI-only state from *doc* into a :class:`GuiOverlay`."""
    return GuiOverlay(
        notes=doc.description.notes,
        tasks=list(doc.description.tasks),
        ocr_text=doc.description.ocr_text,
        markdown=doc.description.markdown,
        split_markers=list(doc.split_markers),
        reviewed=doc.review.reviewed,
        reviewed_at=doc.review.reviewed_at,
        gui_status=doc.status,
        recipient=str(doc.metadata.recipient.value or ""),
        reference=str(doc.metadata.reference.value or ""),
        location=str(doc.metadata.location.value or ""),
        amount=str(doc.metadata.amount.value or ""),
        confidentiality=doc.metadata.confidentiality,
    )
