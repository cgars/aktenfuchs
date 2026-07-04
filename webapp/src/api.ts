import type { QueueItem, ReviewDocument } from './types'

const API_BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || `Request failed: ${response.status}`)
  }
  return (await response.json()) as T
}

export function listDocuments() {
  return request<QueueItem[]>('/documents')
}

export function getDocument(id: string) {
  return request<ReviewDocument>(`/documents/${id}`)
}

export function saveDocument(doc: ReviewDocument) {
  return request<ReviewDocument>(`/documents/${doc.id}`, {
    method: 'PUT',
    body: JSON.stringify(doc),
  })
}

export function approveDocument(id: string) {
  return request<ReviewDocument>(`/documents/${id}/approve`, { method: 'POST' })
}

export function markNeedsSplitReview(id: string) {
  return request<ReviewDocument>(`/documents/${id}/mark-needs-split-review`, { method: 'POST' })
}

export function rerunAnalysis(id: string) {
  return request<{ status: string; message: string }>(`/documents/${id}/rerun-analysis`, { method: 'POST' })
}

export function getPdfUrl(id: string) {
  return `${API_BASE}/documents/${id}/pdf`
}
