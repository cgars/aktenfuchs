"""Tests for the Aktenfux GUI FastAPI backend."""
from __future__ import annotations

from fastapi.testclient import TestClient

from aktenfux.gui_api import app


client = TestClient(app)


def test_list_documents_returns_queue_items() -> None:
    response = client.get('/api/documents')
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert {'id', 'source_file', 'status'}.issubset(payload[0].keys())


def test_get_and_update_document_roundtrip() -> None:
    docs = client.get('/api/documents').json()
    doc_id = docs[0]['id']

    original = client.get(f'/api/documents/{doc_id}').json()
    assert original['id'] == doc_id

    updated = dict(original)
    updated['description'] = dict(original['description'])
    updated['description']['notes'] = 'Updated from API test'

    put_response = client.put(f'/api/documents/{doc_id}', json=updated)
    assert put_response.status_code == 200
    assert put_response.json()['description']['notes'] == 'Updated from API test'

    restore_response = client.put(f'/api/documents/{doc_id}', json=original)
    assert restore_response.status_code == 200


def test_rerun_analysis_placeholder() -> None:
    docs = client.get('/api/documents').json()
    doc_id = docs[0]['id']

    response = client.post(f'/api/documents/{doc_id}/rerun-analysis')
    assert response.status_code == 200
    assert response.json()['status'] == 'not_implemented'
