import { useCallback, useRef, useState } from 'react'
import { streamChat } from '../api/chat'
import type { Citation } from '../types/api'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
}

export interface UseChatResult {
  messages: ChatMessage[]
  streaming: boolean
  conversationId: number | null
  error: string | null
  send: (question: string) => Promise<void>
  stop: () => void
  reset: () => void
}

export function useChat(): UseChatResult {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streaming, setStreaming] = useState(false)
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const send = useCallback(
    async (question: string) => {
      const text = question.trim()
      if (!text || streaming) return

      setError(null)
      setStreaming(true)
      setMessages((prev) => [
        ...prev,
        { role: 'user', content: text, citations: [] },
        { role: 'assistant', content: '', citations: [] },
      ])

      const controller = new AbortController()
      abortRef.current = controller

      await streamChat(
        {
          question: text,
          conversation_id: conversationId,
          top_k: 5,
        },
        {
          onSources: (citations) => {
            setMessages((prev) => {
              if (prev.length === 0) return prev
              const last = { ...prev[prev.length - 1], citations }
              return [...prev.slice(0, -1), last]
            })
          },
          onToken: (piece) => {
            setMessages((prev) => {
              if (prev.length === 0) return prev
              const last = { ...prev[prev.length - 1], content: prev[prev.length - 1].content + piece }
              return [...prev.slice(0, -1), last]
            })
          },
          onDone: (info) => {
            setConversationId(info.conversation_id)
          },
          onError: (message) => {
            setError(message)
          },
        },
        controller.signal,
      )

      abortRef.current = null
      setStreaming(false)
    },
    [conversationId, streaming],
  )

  const stop = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setStreaming(false)
  }, [])

  const reset = useCallback(() => {
    stop()
    setMessages([])
    setConversationId(null)
    setError(null)
  }, [stop])

  return { messages, streaming, conversationId, error, send, stop, reset }
}
