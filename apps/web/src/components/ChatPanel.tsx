import { useEffect, useRef, useState } from 'react'
import { useChat } from '../hooks/useChat'
import { MessageBubble } from './MessageBubble'

export function ChatPanel() {
  const { messages, streaming, error, send, stop, reset } = useChat()
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    const text = input
    setInput('')
    await send(text)
  }

  return (
    <section className="chat">
      <header className="chat-header">
        <h2>问答</h2>
        <button className="link" onClick={reset} disabled={streaming}>
          新会话
        </button>
      </header>

      <div className="chat-body">
        {messages.length === 0 && (
          <p className="muted">先上传几份资料，然后在这里提问。回答会附带引用来源。</p>
        )}
        {messages.map((message, index) => (
          <MessageBubble key={index} message={message} />
        ))}
        <div ref={bottomRef} />
      </div>

      {error && <p className="error">{error}</p>}

      <form className="chat-input" onSubmit={handleSubmit}>
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="问点什么…（Enter 发送，Shift+Enter 换行）"
          rows={3}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              void handleSubmit(event)
            }
          }}
        />
        {streaming ? (
          <button type="button" className="secondary" onClick={stop}>
            停止
          </button>
        ) : (
          <button type="submit" disabled={!input.trim()}>
            发送
          </button>
        )}
      </form>
    </section>
  )
}
