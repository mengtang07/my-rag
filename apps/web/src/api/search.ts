import { request } from './client'
import type { SearchHit } from '../types/api'

export interface SearchResult {
  query: string
  hits: SearchHit[]
  took_ms: number
}

export async function search(query: string, topK = 5): Promise<SearchResult> {
  return request<SearchResult>('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: topK }),
  })
}
