import { Fragment, useEffect, useRef } from 'react'
import type { ChatMessage } from '../../types/chat'
import { renderModelResponse } from '../../utils/markdown'

interface MessageListProps {
  messages: ChatMessage[]
}

export function MessageList({ messages }: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const el = containerRef.current
    el.scrollTo({
      top: el.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages])

  return (
    <div className="chat-messages" ref={containerRef}>
      {messages.length === 0 && (
        <div className="welcome-message">
          <div className="welcome-content">
            <h2 className="welcome-logo">
              <span className="logo-health">Health</span>
              <span className="logo-navy">Navy</span>
            </h2>
            <h3>Welcome to HealthNavy</h3>
            <p>
              How can I assist you today? Ask clinical questions, review treatment options, or explore guidelines.
            </p>
          </div>
        </div>
      )}

      {messages.map((message) => {
        if (message.author === 'assistant') {
          return (
            <div key={message.id} className="message ai-message">
              <div
                className="message-content"
                dangerouslySetInnerHTML={{
                  __html: renderModelResponse(message.content),
                }}
              />
            </div>
          )
        }

        if (message.author === 'error') {
          return (
            <div key={message.id} className="message error-message">
              <div className="message-content">
                <strong>⚠️ Error:</strong>
                <p>{message.content}</p>
              </div>
            </div>
          )
        }

        if (message.author === 'system') {
          return (
            <div key={message.id} className="message system-message">
              <div className="message-content">{message.content}</div>
            </div>
          )
        }

        return (
          <Fragment key={message.id}>
            <div className="message user-message">
              <div className="message-content">
                {message.content.split('\n').map((line, index) => (
                  <span key={`${message.id}-${index}`}>
                    {line}
                    <br />
                  </span>
                ))}
              </div>
            </div>
          </Fragment>
        )
      })}
    </div>
  )
}

