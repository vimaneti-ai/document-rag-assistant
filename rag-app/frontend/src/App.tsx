import { FormEvent, useEffect, useMemo, useState } from 'react'
import { clearIndex, getStatus, sendMessage, uploadDocument } from './api/client'
import { ChatWindow } from './components/ChatWindow'
import { Sidebar } from './components/Sidebar'
import type { Message, StatusResponse, UsageStats } from './types'

const emptyStatus: StatusResponse = {
  document_loaded: false,
  document_name: null,
  total_chunks: 0,
}

export default function App() {
  const [status, setStatus] = useState<StatusResponse>(emptyStatus)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionCost, setSessionCost] = useState(0)
  const [cacheHits, setCacheHits] = useState(0)
  const [lastUsage, setLastUsage] = useState<UsageStats | undefined>()

  useEffect(() => {
    void refreshStatus()
  }, [])

  const questionsAsked = useMemo(
    () => messages.filter((message) => message.role === 'user').length,
    [messages],
  )

  async function refreshStatus() {
    const nextStatus = await getStatus()
    setStatus(nextStatus)
  }

  async function handleUpload(file: File) {
    setError(null)
    setIsUploading(true)
    try {
      const uploaded = await uploadDocument(file)
      setStatus({
        document_loaded: true,
        document_name: uploaded.filename,
        total_chunks: uploaded.chunks,
      })
      setMessages([
        {
          role: 'assistant',
          content: `Document indexed: ${uploaded.filename}\n\n${uploaded.summary}`,
        },
      ])
      setSessionCost(0)
      setCacheHits(0)
      setLastUsage(undefined)
    } catch (err) {
      setError(readError(err))
    } finally {
      setIsUploading(false)
    }
  }

  async function handleSend(event: FormEvent) {
    event.preventDefault()
    const question = input.trim()
    if (!question || isLoading || !status.document_loaded) return

    setError(null)
    setInput('')
    const userMessage: Message = { role: 'user', content: question }
    const nextMessages = [...messages, userMessage]
    setMessages(nextMessages)
    setIsLoading(true)

    try {
      const response = await sendMessage(question, messages)
      const assistantMessage: Message = {
        role: 'assistant',
        content: response.answer,
        usage: response.usage,
        sources: response.sources,
      }
      setMessages([...nextMessages, assistantMessage])
      setSessionCost((cost) => cost + response.usage.cost_usd)
      setCacheHits((hits) => hits + (response.usage.cache_hit ? 1 : 0))
      setLastUsage(response.usage)
    } catch (err) {
      setError(readError(err))
      setMessages(nextMessages)
    } finally {
      setIsLoading(false)
    }
  }

  async function handleClear() {
    setError(null)
    await clearIndex()
    setStatus(emptyStatus)
    setMessages([])
    setInput('')
    setSessionCost(0)
    setCacheHits(0)
    setLastUsage(undefined)
  }

  return (
    <div className="flex min-h-screen flex-col bg-ink-900 text-slate-100 lg:flex-row">
      <Sidebar
        status={status}
        isUploading={isUploading}
        totalCost={sessionCost}
        totalQuestions={questionsAsked}
        cacheHits={cacheHits}
        lastUsage={lastUsage}
        onUpload={handleUpload}
        onClear={handleClear}
      />
      <main className="flex min-h-screen flex-1 flex-col bg-[radial-gradient(circle_at_top_left,rgba(47,124,246,0.14),transparent_34%),#0b0f18]">
        <KpiRow
          questionsAsked={questionsAsked}
          cacheHits={cacheHits}
          totalCost={sessionCost}
          documentLoaded={status.document_loaded}
        />
        {error && <div className="mx-5 mt-4 rounded border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-100 lg:mx-8">{error}</div>}
        {status.document_loaded ? (
          <>
            <ChatWindow messages={messages} isLoading={isLoading} />
            <form className="border-t border-white/10 bg-ink-900/85 px-5 py-4 backdrop-blur lg:px-8" onSubmit={handleSend}>
              <div className="mx-auto flex max-w-4xl gap-3">
                <input
                  className="chat-input"
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="Ask a question about the uploaded document..."
                  disabled={isLoading}
                />
                <button className="send-button" disabled={isLoading || !input.trim()}>
                  Send
                </button>
              </div>
            </form>
          </>
        ) : (
          <EmptyState />
        )}
      </main>
    </div>
  )
}

function KpiRow({
  questionsAsked,
  cacheHits,
  totalCost,
  documentLoaded,
}: {
  questionsAsked: number
  cacheHits: number
  totalCost: number
  documentLoaded: boolean
}) {
  return (
    <div className="grid gap-3 border-b border-white/10 px-5 py-4 sm:grid-cols-2 xl:grid-cols-4 lg:px-8">
      <Kpi label="Questions" value={questionsAsked.toString()} />
      <Kpi label="Cache hits" value={cacheHits.toString()} tone={cacheHits ? 'good' : undefined} />
      <Kpi label="Total cost" value={`$${totalCost.toFixed(5)}`} />
      <Kpi label="Model" value="claude-haiku-4-5" tone={documentLoaded ? 'good' : undefined} />
    </div>
  )
}

function Kpi({ label, value, tone }: { label: string; value: string; tone?: 'good' }) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.04] px-4 py-3">
      <div className="text-xs uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`mt-1 truncate text-lg font-semibold ${tone === 'good' ? 'text-emerald-300' : 'text-slate-100'}`}>
        {value}
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-1 items-center justify-center px-5 py-10">
      <div className="max-w-3xl text-center">
        <p className="text-sm font-semibold uppercase tracking-[0.24em] text-accent-400">Ready for retrieval</p>
        <h2 className="mt-4 text-4xl font-semibold tracking-normal text-white sm:text-5xl">Upload a document to start a grounded chat.</h2>
        <div className="mt-8 grid gap-3 text-left sm:grid-cols-3">
          <Feature title="Local vectors" body="FAISS and MiniLM embeddings run on your Mac." />
          <Feature title="Cached context" body="Claude prompt caching lowers repeated input cost." />
          <Feature title="Traceable answers" body="Every response can expose the retrieved source chunks." />
        </div>
      </div>
    </div>
  )
}

function Feature({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.04] p-4">
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-400">{body}</p>
    </div>
  )
}

function readError(error: unknown) {
  if (typeof error === 'object' && error && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response
    return response?.data?.detail || 'Request failed.'
  }
  return error instanceof Error ? error.message : 'Something went wrong.'
}
