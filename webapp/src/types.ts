export type DocumentStatus =
  | 'imported'
  | 'ocr_done'
  | 'ai_described'
  | 'needs_review'
  | 'needs_split_review'
  | 'metadata_review'
  | 'approved'
  | 'archived'

export type MetadataState = 'empty' | 'suggested' | 'confirmed'

export interface MetadataValue {
  value: string | number | null
  state: MetadataState
  confidence: number | null
}

export interface TaskItem {
  label: string
  done: boolean
}

export interface ReviewDocument {
  id: string
  source_file: string
  pdf_path: string
  pages: number[]
  status: DocumentStatus
  split_markers: number[]
  description: {
    summary: string
    markdown: string
    ocr_text: string
    notes: string
    tasks: TaskItem[]
  }
  metadata: {
    document_type: MetadataValue
    date: MetadataValue
    sender: MetadataValue
    recipient: MetadataValue
    subject: MetadataValue
    reference: MetadataValue
    amount: MetadataValue
    deadline: MetadataValue
    location: MetadataValue
    persons: string[]
    organizations: string[]
    tags: string[]
    confidentiality: string
    suggested_archive_path: string
    status: DocumentStatus
  }
  review: {
    reviewed: boolean
    reviewed_at: string | null
  }
}

export interface QueueItem {
  id: string
  source_file: string
  status: DocumentStatus
}
