"""Pydantic models for the Aktenfux review GUI MVP."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

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
    "Brief",
    "Bescheid",
    "Rechnung",
    "Vertrag",
    "Bank",
    "Versicherung",
    "Steuer",
    "Gesundheit",
    "Wohnen",
    "Arbeit",
    "Garantie",
    "Anleitung",
    "Sonstiges",
]
