import { apiDelete, apiGet, apiPost } from '@/lib/api'

export interface ConversationSummary {
  id: string
  title: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations: { type: string; id?: string; source_id?: string; tool?: string }[]
  tool_name?: string
  created_at: string
}

export const listConversations = () => apiGet<{ results: ConversationSummary[] }>('/api/assistant/conversations/')
export const createConversation = (title = '') =>
  apiPost<ConversationSummary>('/api/assistant/conversations/', { title })
export const getConversation = (id: string) =>
  apiGet<{ id: string; title: string; messages: ChatMessage[] }>(`/api/assistant/conversations/${id}/`)
export const deleteConversation = (id: string) => apiDelete(`/api/assistant/conversations/${id}/`)
export const sendMessage = (id: string, content: string) =>
  apiPost<{ reply: string; tools_used: string[]; citations: ChatMessage['citations']; grounding: string }>(
    `/api/assistant/conversations/${id}/messages/`,
    { content },
  )
