import { useState } from 'react'
import type { Message, UsageStats } from '../types'

interface ChatWindowProps {
  messages: Message[]
  isLoading: boolean
}

export function ChatWindow({ messages, isLoading }: ChatWindowProps) {
  return (
    <div className="flex-1 overflow-y-auto px-5 py-5 lg:px-8">
      <div className="mx-auto flex max-w-4xl flex-col gap-4">
        {messages.map((message, index) => (
          <MessageBubble key={`${message.role}-${index}`} message={message} />
        ))}
        {isLoading && (
          <div className="assistant-card w-fit">
            <div className="typing-indicator">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: Message }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] rounded bg-accent-500 px-4 py-3 text-sm leading-6 text-white shadow-lg shadow-accent-500/10">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="assistant-card">
      <div className="whitespace-pre-wrap text-sm leading-7 text-slate-100">{message.content}</div>
      {message.usage && <Usage usage={message.usage} />}
      {message.sources?.length ? <Sources sources={message.sources} /> : null}
    </div>
  )
}

function Usage({ usage }: { usage: UsageStats }) {
  return (
    <div className="mt-4 flex flex-wrap gap-2 border-t border-white/10 pt-3 text-[11px] text-slate-400">
      <span className={usage.cache_hit ? 'usage-good' : 'usage-warn'}>
        {usage.cache_hit ? 'Cache hit' : 'Cache write'}
      </span>
      <span>{usage.input_tokens} input</span>
      <span>{usage.output_tokens} output</span>
      <span>{usage.cache_read_tokens} cache read</span>
      <span>{usage.cache_write_tokens} cache write</span>
      <span>${usage.cost_usd.toFixed(6)}</span>
    </div>
  )
}

function Sources({ sources }: { sources: string[] }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-3">
      <button className="source-toggle" onClick={() => setOpen((value) => !value)}>
        Sources {open ? 'close' : 'open'}
      </button>
      {open && (
        <ul className="mt-2 space-y-2">
          {sources.map((source) => (
            <li key={source} className="rounded border border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-300">
              {source}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
