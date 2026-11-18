import { request } from './client'
import type { DocumentBrief, DocumentIngestResponse, PageResult } from '../types/api'

export async function listDocuments(): Promise<PageResult<DocumentBrief>> {
  return request<PageResult<DocumentBrief>>('/api/documents?page_size=100')
}

export async function uploadDocument(file: File): Promise<DocumentIngestResponse> {
  const form = new FormData()
  form.append('file', file)
  // 刻意不手动设 Content-Type：浏览器要自己带 multipart 的 boundary
  return request<DocumentIngestResponse>('/api/documents', {
    method: 'POST',
    body: form,
  })
}

export async function deleteDocument(id: number): Promise<void> {
  await request<null>(`/api/documents/${id}`, { method: 'DELETE' })
}
