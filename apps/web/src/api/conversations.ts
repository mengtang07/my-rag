import { request } from './client'
import type { ConversationBrief, PageResult } from '../types/api'

export async function listConversations(): Promise<PageResult<ConversationBrief>> {
  return request<PageResult<ConversationBrief>>('/api/conversations?page_size=50')
}

export async function deleteConversation(id: number): Promise<void> {
  await request<null>(`/api/conversations/${id}`, { method: 'DELETE' })
}
