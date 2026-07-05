"""FastAPI backend for the Aktenfux review GUI MVP."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from aktenfux.config import load_config
from aktenfux.gui_models import DOCUMENT_TYPE_OPTIONS, ReviewDocument
from aktenfux.gui_storage import GuiDocumentStore

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]

try:
    _config = load_config()
    _data_dir = _config.base_dir
    _base_dir = _config.base_dir
except FileNotFoundError:
    _data_dir = _PACKAGE_ROOT / "mock_data" / "documents"
    _base_dir = _PACKAGE_ROOT

app = FastAPI(title="Aktenfux GUI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = GuiDocumentStore(_data_dir, _base_dir)

# TODO hooks for future pipeline integration:
# - OCR pipeline
# - AI description generation
# - Metadata extraction
# - Actual PDF split/merge execution
# - Archive export

@app.get("/api/documents")
def list_documents():
    return store.list_documents()


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str):
    return store.get_document(doc_id)


@app.put("/api/documents/{doc_id}")
def update_document(doc_id: str, document: ReviewDocument):
    return store.save_document(doc_id, document)


@app.post("/api/documents/{doc_id}/approve")
def approve_document(doc_id: str):
    return store.approve_document(doc_id)


@app.post("/api/documents/{doc_id}/mark-needs-split-review")
def mark_needs_split_review(doc_id: str):
    return store.mark_needs_split_review(doc_id)


@app.post("/api/documents/{doc_id}/rerun-analysis")
def rerun_analysis(doc_id: str):
    store.get_document(doc_id)
    # TODO: Connect OCR + AI analysis pipeline hook.
    return {
        "status": "not_implemented",
        "message": "AI analysis pipeline hook not implemented yet",
    }


@app.get("/api/documents/{doc_id}/pdf")
def get_document_pdf(doc_id: str):
    document = store.get_document(doc_id)
    pdf_path = store.resolve_pdf_path(document)
    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_path.name)


@app.get("/api/document-types")
def get_document_types():
    return DOCUMENT_TYPE_OPTIONS
