import type { Citation } from '../types/api'

export interface ChatRequestBody {
  question: string
  conversation_id?: number | null
  top_k?: number
}

export interface ChatHandlers {
  onSources?: (citations: Citation[]) => void
  onToken?: (text: string) => void
  onDone?: (info: { conversation_id: number; message_id: number }) => void
  onError?: (message: string) => void
}

/**
 * SSE 流式对话。
 *
 * `EventSource` 只能发 GET，而聊天是 POST，所以必须用 fetch + ReadableStream
 * 自己拆 SSE 帧：按空行切帧，再解析 `event:` / `data:` 两行。
 */
export async function streamChat(
  body: ChatRequestBody,
  handlers: ChatHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response
  try {
    response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if ((error as Error).name === 'AbortError') return
    handlers.onError?.('连接失败')
    return
  }

  if (!response.ok || !response.body) {
    handlers.onError?.(`请求失败（HTTP ${response.status}）`)
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        handleFrame(frame, handlers)
        boundary = buffer.indexOf('\n\n')
      }
    }
  } catch (error) {
    if ((error as Error).name !== 'AbortError') {
      handlers.onError?.('连接中断')
    }
  }
}

function handleFrame(frame: string, handlers: ChatHandlers): void {
  let event = 'message'
  const dataLines: string[] = []

  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trim())
    }
  }

  if (dataLines.length === 0) return

  let payload: Record<string, unknown>
  try {
    payload = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
  } catch {
    return
  }

  switch (event) {
    case 'sources':
      handlers.onSources?.((payload.citations as Citation[]) ?? [])
      break
    case 'token':
      handlers.onToken?.((payload.text as string) ?? '')
      break
    case 'done':
      handlers.onDone?.(payload as unknown as { conversation_id: number; message_id: number })
      break
    case 'error':
      handlers.onError?.((payload.message as string) ?? '出错了')
      break
    default:
      break
  }
}
