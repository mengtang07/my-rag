import type { ChatMessage } from '../hooks/useChat'
import { SourceList } from './SourceList'

interface MessageBubbleProps {
  message: ChatMessage
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`bubble ${isUser ? 'bubble-user' : 'bubble-assistant'}`}>
      <div className="bubble-role">{isUser ? '我' : '助手'}</div>
      <div className="bubble-content">
        {message.content ? (
          <pre>{message.content}</pre>
        ) : (
          <span className="muted">思考中…</span>
        )}
      </div>
      {!isUser && <SourceList citations={message.citations} />}
    </div>
  )
}
