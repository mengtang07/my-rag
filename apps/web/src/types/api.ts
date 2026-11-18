/** 与后端 pydantic schema 一一对应的类型 */

export interface ApiEnvelope<T> {
  code: string
  data: T
  message: string
}

export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface DocumentBrief {
  id: number
  title: string
  filename: string
  file_type: string | null
  file_size: number
  status: string
  chunk_count: number
  created_at: string
}

export interface DocumentIngestResponse {
  document_id: number
  title: string
  status: string
  chunk_count: number
  reused: boolean
  message: string
}

export interface SearchHit {
  chunk_id: number
  document_id: number
  document_title: string
  heading_path: string
  page_number: number | null
  content: string
  score: number
}

export interface Citation {
  index: number
  chunk_id: number
  document_id: number
  document_title: string
  heading_path: string
  page_number: number | null
  score: number
}

export interface ChatResponse {
  conversation_id: number
  message_id: number
  answer: string
  citations: Citation[]
}

export interface ConversationBrief {
  id: number
  title: string
  created_at: string
  updated_at: string
}
