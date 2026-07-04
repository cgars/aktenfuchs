import { useEffect, useMemo, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { approveDocument, getDocument, getPdfUrl, listDocuments, markNeedsSplitReview, rerunAnalysis, saveDocument } from './api'
import type { MetadataValue, QueueItem, ReviewDocument } from './types'

pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString()

type DescriptionTab = 'Summary' | 'OCR Text' | 'Markdown' | 'Notes' | 'Tasks'

const STATUS_OPTIONS = [
  'imported',
  'ocr_done',
  'ai_described',
  'needs_review',
  'needs_split_review',
  'metadata_review',
  'approved',
  'archived',
] as const

const DOCUMENT_TYPE_OPTIONS = [
  'Brief',
  'Bescheid',
  'Rechnung',
  'Vertrag',
  'Bank',
  'Versicherung',
  'Steuer',
  'Gesundheit',
  'Wohnen',
  'Arbeit',
  'Garantie',
  'Anleitung',
  'Sonstiges',
]

function App() {
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [index, setIndex] = useState(0)
  const [doc, setDoc] = useState<ReviewDocument | null>(null)
  const [activeTab, setActiveTab] = useState<DescriptionTab>('Summary')
  const [page, setPage] = useState(1)
  const [pageCount, setPageCount] = useState(1)
  const [zoom, setZoom] = useState(1)
  const [rotation, setRotation] = useState(0)
  const [message, setMessage] = useState('')
  const [showShortcuts, setShowShortcuts] = useState(false)
  const [focusedPanel, setFocusedPanel] = useState<'pdf' | 'description' | 'metadata'>('pdf')

  const pdfPanelRef = useRef<HTMLDivElement>(null)
  const descriptionPanelRef = useRef<HTMLDivElement>(null)
  const metadataPanelRef = useRef<HTMLDivElement>(null)

  const currentQueueItem = queue[index]

  useEffect(() => {
    void (async () => {
      const docs = await listDocuments()
      setQueue(docs)
      if (docs.length > 0) {
        const full = await getDocument(docs[0].id)
        setDoc(full)
      }
    })()
  }, [])

  useEffect(() => {
    if (!currentQueueItem) return
    void (async () => {
      const full = await getDocument(currentQueueItem.id)
      setDoc(full)
      setPage(1)
      setZoom(1)
      setRotation(0)
    })()
  }, [currentQueueItem])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const typing = !!target && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))
      if (typing) {
        if (event.key === 'Escape') {
          ;(target as HTMLInputElement).blur?.()
        }
        return
      }

      if (event.key === '?') {
        event.preventDefault()
        setShowShortcuts((value) => !value)
        return
      }

      if (event.key === 'Escape') {
        setShowShortcuts(false)
      }

      if (event.ctrlKey && event.key.toLowerCase() === 's') {
        event.preventDefault()
        void handleSave()
        return
      }

      if (event.ctrlKey && event.key === 'Enter') {
        event.preventDefault()
        void handleSaveAndNext()
        return
      }

      if (event.ctrlKey && event.key === '1') {
        event.preventDefault()
        focusPanel('pdf')
        return
      }
      if (event.ctrlKey && event.key === '2') {
        event.preventDefault()
        focusPanel('description')
        return
      }
      if (event.ctrlKey && event.key === '3') {
        event.preventDefault()
        focusPanel('metadata')
        return
      }

      if (event.key === 'ArrowRight') {
        event.preventDefault()
        goToDocument(index + 1)
        return
      }
      if (event.key === 'ArrowLeft') {
        event.preventDefault()
        goToDocument(index - 1)
        return
      }

      if (event.key === '+' || event.key === '=') {
        event.preventDefault()
        setZoom((value) => Math.min(value + 0.1, 3))
      }
      if (event.key === '-') {
        event.preventDefault()
        setZoom((value) => Math.max(value - 0.1, 0.5))
      }
      if (event.key.toLowerCase() === 'r') {
        event.preventDefault()
        setRotation((value) => (value + 90) % 360)
      }
      if (event.key.toLowerCase() === 't') {
        event.preventDefault()
        toggleSplitMarker()
      }
      if (event.key === 'PageDown') {
        event.preventDefault()
        setPage((value) => Math.min(value + 1, pageCount))
      }
      if (event.key === 'PageUp') {
        event.preventDefault()
        setPage((value) => Math.max(value - 1, 1))
      }
      if (event.key.toLowerCase() === 'm') {
        event.preventDefault()
        focusPanel('metadata')
      }
      if (event.key.toLowerCase() === 'e') {
        event.preventDefault()
        setActiveTab('Summary')
        focusPanel('description')
      }
      if (event.key.toLowerCase() === 'n') {
        event.preventDefault()
        setActiveTab('Notes')
        focusPanel('description')
      }
      if (event.key.toLowerCase() === 'o') {
        event.preventDefault()
        setActiveTab('OCR Text')
        focusPanel('description')
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  })

  const splitMarkers = useMemo(() => doc?.split_markers ?? [], [doc?.split_markers])

  const updateMetadataValue = (field: keyof ReviewDocument['metadata'], next: Partial<MetadataValue>) => {
    if (!doc) return
    const currentValue = doc.metadata[field] as MetadataValue
    setDoc({
      ...doc,
      metadata: {
        ...doc.metadata,
        [field]: {
          ...currentValue,
          ...next,
        },
      },
    })
  }

  const updateSimpleMetadataArray = (field: 'persons' | 'organizations' | 'tags', value: string) => {
    if (!doc) return
    setDoc({
      ...doc,
      metadata: {
        ...doc.metadata,
        [field]: value
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
      },
    })
  }

  const goToDocument = (nextIndex: number) => {
    if (nextIndex < 0 || nextIndex >= queue.length) return
    setIndex(nextIndex)
  }

  const handleSave = async () => {
    if (!doc) return
    const saved = await saveDocument(doc)
    setDoc(saved)
    setQueue((items) => items.map((item) => (item.id === saved.id ? { ...item, status: saved.status } : item)))
    setMessage('Saved')
  }

  const handleSaveAndNext = async () => {
    await handleSave()
    goToDocument(index + 1)
  }

  const handleApprove = async () => {
    if (!doc) return
    const updated = await approveDocument(doc.id)
    setDoc(updated)
    setQueue((items) => items.map((item) => (item.id === updated.id ? { ...item, status: updated.status } : item)))
    setMessage('Marked as approved')
  }

  const handleNeedsSplitReview = async () => {
    if (!doc) return
    const updated = await markNeedsSplitReview(doc.id)
    setDoc(updated)
    setQueue((items) => items.map((item) => (item.id === updated.id ? { ...item, status: updated.status } : item)))
    setMessage('Marked as needs split review')
  }

  const handleRerunAnalysis = async () => {
    if (!doc) return
    const result = await rerunAnalysis(doc.id)
    setMessage(result.message)
  }

  const toggleSplitMarker = () => {
    if (!doc) return
    const existing = new Set(doc.split_markers)
    if (page > 1) {
      if (existing.has(page)) {
        existing.delete(page)
      } else {
        existing.add(page)
      }
      setDoc({ ...doc, split_markers: [...existing].sort((a, b) => a - b) })
    }
  }

  const focusPanel = (panel: 'pdf' | 'description' | 'metadata') => {
    setFocusedPanel(panel)
    if (panel === 'pdf') pdfPanelRef.current?.focus()
    if (panel === 'description') descriptionPanelRef.current?.focus()
    if (panel === 'metadata') metadataPanelRef.current?.focus()
  }

  if (!doc) {
    return <div className="loading">Loading documents…</div>
  }

  return (
    <div className="app-shell">
      <header className="toolbar">
        <button onClick={() => goToDocument(index - 1)} disabled={index === 0}>Previous document</button>
        <button onClick={() => void handleSave()}>Save</button>
        <button onClick={() => void handleSaveAndNext()}>Save and next</button>
        <button onClick={() => void handleApprove()}>Mark as approved</button>
        <button onClick={() => void handleNeedsSplitReview()}>Mark as needs split review</button>
        <button onClick={() => void handleRerunAnalysis()}>Re-run analysis</button>
        <button onClick={() => goToDocument(index + 1)} disabled={index >= queue.length - 1}>Next document</button>
        <span className="status">{doc.id} · {doc.status} · {message}</span>
      </header>

      <aside className="queue">
        {queue.map((item, queueIndex) => (
          <button
            key={item.id}
            className={queueIndex === index ? 'queue-item active' : 'queue-item'}
            onClick={() => goToDocument(queueIndex)}
          >
            <span>{item.id}</span>
            <small>{item.status}</small>
          </button>
        ))}
      </aside>

      <main className="panels">
        <section
          ref={pdfPanelRef}
          tabIndex={-1}
          className={`panel pdf ${focusedPanel === 'pdf' ? 'focused' : ''}`}
          onClick={() => focusPanel('pdf')}
        >
          <h2>PDF / Scan</h2>
          <div className="pdf-controls">
            <button onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous page</button>
            <button onClick={() => setPage((value) => Math.min(pageCount, value + 1))}>Next page</button>
            <button onClick={() => setZoom((value) => Math.min(value + 0.1, 3))}>Zoom +</button>
            <button onClick={() => setZoom((value) => Math.max(value - 0.1, 0.5))}>Zoom -</button>
            <button onClick={() => setRotation((value) => (value + 90) % 360)}>Rotate</button>
            <button onClick={toggleSplitMarker}>Split before this page</button>
          </div>
          <p className="meta-line">
            Page {page} / {pageCount} · Zoom {zoom.toFixed(1)}x · Rotation {rotation}°
          </p>
          <p className="meta-line">Split markers: {splitMarkers.length ? splitMarkers.join(', ') : 'none'}</p>
          <div className="pdf-viewer">
            <Document file={getPdfUrl(doc.id)} onLoadSuccess={({ numPages }) => setPageCount(numPages)}>
              <Page pageNumber={page} scale={zoom} rotate={rotation} renderAnnotationLayer renderTextLayer />
            </Document>
          </div>
        </section>

        <section
          ref={descriptionPanelRef}
          tabIndex={-1}
          className={`panel description ${focusedPanel === 'description' ? 'focused' : ''}`}
          onClick={() => focusPanel('description')}
        >
          <h2>Description / OCR / Markdown</h2>
          <div className="tabs">
            {(['Summary', 'OCR Text', 'Markdown', 'Notes', 'Tasks'] as DescriptionTab[]).map((tab) => (
              <button key={tab} className={activeTab === tab ? 'tab active' : 'tab'} onClick={() => setActiveTab(tab)}>{tab}</button>
            ))}
          </div>
          {activeTab === 'Summary' && (
            <textarea value={doc.description.summary} onChange={(event) => setDoc({ ...doc, description: { ...doc.description, summary: event.target.value } })} />
          )}
          {activeTab === 'OCR Text' && (
            <textarea value={doc.description.ocr_text} onChange={(event) => setDoc({ ...doc, description: { ...doc.description, ocr_text: event.target.value } })} />
          )}
          {activeTab === 'Markdown' && (
            <textarea value={doc.description.markdown} onChange={(event) => setDoc({ ...doc, description: { ...doc.description, markdown: event.target.value } })} />
          )}
          {activeTab === 'Notes' && (
            <textarea value={doc.description.notes} onChange={(event) => setDoc({ ...doc, description: { ...doc.description, notes: event.target.value } })} />
          )}
          {activeTab === 'Tasks' && (
            <div className="tasks">
              {doc.description.tasks.map((task, taskIndex) => (
                <label key={`${task.label}-${taskIndex}`}>
                  <input
                    type="checkbox"
                    checked={task.done}
                    onChange={(event) => {
                      const next = [...doc.description.tasks]
                      next[taskIndex] = { ...task, done: event.target.checked }
                      setDoc({ ...doc, description: { ...doc.description, tasks: next } })
                    }}
                  />
                  <input
                    value={task.label}
                    onChange={(event) => {
                      const next = [...doc.description.tasks]
                      next[taskIndex] = { ...task, label: event.target.value }
                      setDoc({ ...doc, description: { ...doc.description, tasks: next } })
                    }}
                  />
                </label>
              ))}
            </div>
          )}
          <div className="actions-row">
            <button onClick={() => setMessage('Description accepted')}>Accept description</button>
            <button onClick={() => setActiveTab('Summary')}>Edit</button>
            <button onClick={() => setMessage('TODO: Regenerate description suggestion')}>Regenerate suggestion</button>
            <button onClick={() => setMessage('TODO: Extract tasks via AI hook')}>Extract tasks</button>
          </div>
        </section>

        <section
          ref={metadataPanelRef}
          tabIndex={-1}
          className={`panel metadata ${focusedPanel === 'metadata' ? 'focused' : ''}`}
          onClick={() => focusPanel('metadata')}
        >
          <h2>Metadata</h2>
          <div className="metadata-grid">
            <label>
              Document type
              <select
                value={String(doc.metadata.document_type.value || '')}
                onChange={(event) => updateMetadataValue('document_type', { value: event.target.value, state: 'confirmed' })}
              >
                <option value="">-</option>
                {DOCUMENT_TYPE_OPTIONS.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
              <StateBadge metadata={doc.metadata.document_type} onConfirm={() => updateMetadataValue('document_type', { state: 'confirmed' })} />
            </label>

            {(['date', 'sender', 'recipient', 'subject', 'reference', 'amount', 'deadline', 'location'] as const).map((field) => (
              <label key={field}>
                {field}
                <input
                  value={doc.metadata[field].value == null ? '' : String(doc.metadata[field].value)}
                  onChange={(event) => updateMetadataValue(field, { value: event.target.value, state: event.target.value ? 'confirmed' : 'empty' })}
                />
                <StateBadge metadata={doc.metadata[field]} onConfirm={() => updateMetadataValue(field, { state: 'confirmed' })} />
              </label>
            ))}

            <label>
              Persons
              <input value={doc.metadata.persons.join(', ')} onChange={(event) => updateSimpleMetadataArray('persons', event.target.value)} />
            </label>
            <label>
              Organizations
              <input value={doc.metadata.organizations.join(', ')} onChange={(event) => updateSimpleMetadataArray('organizations', event.target.value)} />
            </label>
            <label>
              Tags
              <input value={doc.metadata.tags.join(', ')} onChange={(event) => updateSimpleMetadataArray('tags', event.target.value)} />
            </label>
            <label>
              Confidentiality
              <input value={doc.metadata.confidentiality} onChange={(event) => setDoc({ ...doc, metadata: { ...doc.metadata, confidentiality: event.target.value } })} />
            </label>
            <label>
              Suggested archive path
              <input value={doc.metadata.suggested_archive_path} onChange={(event) => setDoc({ ...doc, metadata: { ...doc.metadata, suggested_archive_path: event.target.value } })} />
            </label>
            <label>
              Status
              <select value={doc.status} onChange={(event) => setDoc({ ...doc, status: event.target.value as ReviewDocument['status'], metadata: { ...doc.metadata, status: event.target.value as ReviewDocument['status'] } })}>
                {STATUS_OPTIONS.map((status) => <option key={status} value={status}>{status}</option>)}
              </select>
            </label>
          </div>
        </section>
      </main>

      {showShortcuts && (
        <div className="shortcut-modal" onClick={() => setShowShortcuts(false)}>
          <div className="shortcut-content" onClick={(event) => event.stopPropagation()}>
            <h3>Keyboard shortcuts</h3>
            <ul>
              <li>Ctrl+S save</li>
              <li>Ctrl+Enter save and next</li>
              <li>Ctrl+1/2/3 focus panel</li>
              <li>ArrowLeft/ArrowRight previous/next document</li>
              <li>PageUp/PageDown previous/next page</li>
              <li>+/- zoom · R rotate · T split marker</li>
              <li>E summary · O OCR · N notes · M metadata panel</li>
              <li>Esc close help</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

function StateBadge({ metadata, onConfirm }: { metadata: MetadataValue; onConfirm: () => void }) {
  return (
    <div className="state-row">
      <span className={`state ${metadata.state}`}>{metadata.state}</span>
      {metadata.confidence != null && <small>{metadata.confidence.toFixed(2)}</small>}
      {metadata.state === 'suggested' && <button onClick={onConfirm}>Confirm</button>}
    </div>
  )
}

export default App
