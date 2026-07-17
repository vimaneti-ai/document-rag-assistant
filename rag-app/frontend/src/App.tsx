import { FormEvent, useEffect, useMemo, useState } from 'react'
import {
  clearIndex,
  getOperation,
  getStatus,
  sendMessage,
  uploadDocument,
  type AuthCredentials,
} from './api/client'
import { ChatWindow } from './components/ChatWindow'
import {
  createPendingOperation,
  PipelineVisualizer,
} from './components/PipelineVisualizer'
import { Sidebar } from './components/Sidebar'
import type {
  IngestionVisualization,
  Message,
  PipelineKind,
  PipelineOperation,
  StatusResponse,
  UsageStats,
} from './types'

const emptyStatus: StatusResponse = {
  document_loaded: false,
  document_name: null,
  total_chunks: 0,
}

const storedAuthKey = 'adaptive-rag-basic-auth'
const storedActivityKey = 'adaptive-rag-last-activity'
const inactivityTimeoutMs = readInactivityTimeout()
const activityEvents: Array<keyof WindowEventMap> = [
  'keydown',
  'pointerdown',
  'pointermove',
  'scroll',
  'touchstart',
]

export default function App() {
  const [credentials, setCredentials] = useState<AuthCredentials | null>(() => readStoredAuth())
  const [status, setStatus] = useState<StatusResponse>(emptyStatus)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionCost, setSessionCost] = useState(0)
  const [cacheHits, setCacheHits] = useState(0)
  const [lastUsage, setLastUsage] = useState<UsageStats | undefined>()
  const [pipeline, setPipeline] = useState<PipelineOperation | null>(null)
  const [uploadPipeline, setUploadPipeline] = useState<PipelineOperation | null>(null)
  const [ingestionVisualization, setIngestionVisualization] =
    useState<IngestionVisualization | null>(null)

  useEffect(() => {
    if (credentials) {
      void refreshStatus(credentials)
    }
  }, [credentials])

  useEffect(() => {
    if (!credentials) return

    let timerId: number | undefined
    let lastRecordedAt = readLastActivity() || Date.now()

    function scheduleTimeout() {
      window.clearTimeout(timerId)
      const elapsed = Date.now() - readLastActivity()
      timerId = window.setTimeout(checkForExpiration, Math.max(inactivityTimeoutMs - elapsed, 0))
    }

    function checkForExpiration() {
      if (Date.now() - readLastActivity() >= inactivityTimeoutMs) {
        clearSession(`You were signed out after ${formatTimeout(inactivityTimeoutMs)} of inactivity.`)
        return
      }
      scheduleTimeout()
    }

    function recordActivity() {
      const now = Date.now()
      if (now - lastRecordedAt < 1000) return
      lastRecordedAt = now
      sessionStorage.setItem(storedActivityKey, now.toString())
      scheduleTimeout()
    }

    function checkVisibleTab() {
      if (document.visibilityState === 'visible') {
        checkForExpiration()
      }
    }

    if (!readLastActivity()) {
      sessionStorage.setItem(storedActivityKey, lastRecordedAt.toString())
    }
    activityEvents.forEach((eventName) => {
      window.addEventListener(eventName, recordActivity, { passive: true })
    })
    document.addEventListener('visibilitychange', checkVisibleTab)
    checkForExpiration()

    return () => {
      window.clearTimeout(timerId)
      activityEvents.forEach((eventName) => {
        window.removeEventListener(eventName, recordActivity)
      })
      document.removeEventListener('visibilitychange', checkVisibleTab)
    }
  }, [credentials])

  useEffect(() => {
    if (!credentials || !pipeline || ['completed', 'failed'].includes(pipeline.status)) return

    let cancelled = false
    async function refreshOperation() {
      try {
        const nextOperation = await getOperation(pipeline!.operation_id, credentials!)
        if (!cancelled) {
          setPipeline(nextOperation)
          if (nextOperation.kind === 'upload') setUploadPipeline(nextOperation)
        }
      } catch {
        // The POST request can reach the server just after the first polling attempt.
      }
    }

    void refreshOperation()
    const intervalId = window.setInterval(() => void refreshOperation(), 400)
    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [credentials, pipeline?.operation_id, pipeline?.status])

  const questionsAsked = useMemo(
    () => messages.filter((message) => message.role === 'user').length,
    [messages],
  )

  async function refreshStatus(auth: AuthCredentials) {
    const nextStatus = await getStatus(auth)
    setStatus(nextStatus)
  }

  async function handleLogin(nextCredentials: AuthCredentials) {
    setError(null)
    try {
      const nextStatus = await getStatus(nextCredentials)
      sessionStorage.setItem(storedAuthKey, JSON.stringify(nextCredentials))
      sessionStorage.setItem(storedActivityKey, Date.now().toString())
      setCredentials(nextCredentials)
      setStatus(nextStatus)
    } catch (err) {
      setError(readError(err))
    }
  }

  function handleLogout() {
    clearSession(null)
  }

  function clearSession(message: string | null) {
    sessionStorage.removeItem(storedAuthKey)
    sessionStorage.removeItem(storedActivityKey)
    setCredentials(null)
    setStatus(emptyStatus)
    setMessages([])
    setInput('')
    setSessionCost(0)
    setCacheHits(0)
    setLastUsage(undefined)
    setPipeline(null)
    setUploadPipeline(null)
    setIngestionVisualization(null)
    setError(message)
  }

  async function handleUpload(file: File) {
    if (!credentials) return
    setError(null)
    setIsUploading(true)
    setIngestionVisualization(null)
    const operationId = beginPipeline('upload')
    try {
      const uploaded = await uploadDocument(file, credentials, operationId)
      setPipeline(uploaded.pipeline)
      setUploadPipeline(uploaded.pipeline)
      setIngestionVisualization(uploaded.visualization)
      setStatus({
        document_loaded: true,
        document_name: uploaded.filename,
        total_chunks: uploaded.chunks,
      })
      setMessages([
        {
          role: 'assistant',
          content: `Document indexed: ${uploaded.filename}\n\n${uploaded.summary}`,
          pipeline: uploaded.pipeline,
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
    if (!credentials || !question || isLoading || !status.document_loaded) return

    setError(null)
    setInput('')
    const userMessage: Message = { role: 'user', content: question }
    const nextMessages = [...messages, userMessage]
    setMessages(nextMessages)
    setIsLoading(true)
    const operationId = beginPipeline('chat')

    try {
      const response = await sendMessage(question, messages, credentials, operationId)
      setPipeline(response.pipeline)
      const assistantMessage: Message = {
        role: 'assistant',
        content: response.answer,
        usage: response.usage,
        sources: response.sources,
        pipeline: response.pipeline,
        questionVisualization: response.visualization,
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
    if (!credentials) return
    setError(null)
    await clearIndex(credentials)
    setStatus(emptyStatus)
    setMessages([])
    setInput('')
    setSessionCost(0)
    setCacheHits(0)
    setLastUsage(undefined)
    setPipeline(null)
    setUploadPipeline(null)
    setIngestionVisualization(null)
  }

  function beginPipeline(kind: PipelineKind) {
    const operationId = createOperationId()
    const pendingOperation = createPendingOperation(operationId, kind)
    setPipeline(pendingOperation)
    if (kind === 'upload') setUploadPipeline(pendingOperation)
    return operationId
  }

  if (!credentials) {
    return <LoginScreen error={error} onLogin={handleLogin} />
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
        <div className="flex justify-end border-b border-white/10 px-5 py-3 lg:px-8">
          <button className="source-toggle" onClick={handleLogout}>
            Sign out
          </button>
        </div>
        <KpiRow
          questionsAsked={questionsAsked}
          cacheHits={cacheHits}
          totalCost={sessionCost}
          documentLoaded={status.document_loaded}
        />
        <PipelineVisualizer
          operation={pipeline}
          uploadOperation={uploadPipeline}
          ingestionVisualization={ingestionVisualization}
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

function createOperationId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (character) => {
    const random = Math.floor(Math.random() * 16)
    const value = character === 'x' ? random : (random & 0x3) | 0x8
    return value.toString(16)
  })
}

function LoginScreen({
  error,
  onLogin,
}: {
  error: string | null
  onLogin: (credentials: AuthCredentials) => Promise<void>
}) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setIsSubmitting(true)
    try {
      await onLogin({ username, password })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,rgba(47,124,246,0.18),transparent_34%),#0b0f18] px-5 text-slate-100">
      <form className="w-full max-w-sm rounded border border-white/10 bg-ink-850 p-6 shadow-2xl shadow-black/30" onSubmit={handleSubmit}>
        <div className="mb-6">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded bg-accent-500 text-sm font-black text-white">
            AR
          </div>
          <h1 className="text-xl font-semibold text-white">Adaptive RAG</h1>
          <p className="mt-2 text-sm leading-6 text-slate-400">Sign in to access the document assistant.</p>
        </div>
        {error && <div className="mb-4 rounded border border-red-400/30 bg-red-500/10 px-3 py-2 text-sm text-red-100">{error}</div>}
        <label className="mb-3 block">
          <span className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">Username</span>
          <input
            className="chat-input w-full"
            value={username}
            autoComplete="username"
            onChange={(event) => setUsername(event.target.value)}
            required
          />
        </label>
        <label className="mb-5 block">
          <span className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">Password</span>
          <input
            className="chat-input w-full"
            type="password"
            value={password}
            autoComplete="current-password"
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        <button className="send-button h-11 w-full" disabled={isSubmitting}>
          {isSubmitting ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
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
          <Feature title="Managed vectors" body="Pinecone stores MiniLM embeddings for durable retrieval." />
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

function readStoredAuth(): AuthCredentials | null {
  const raw = sessionStorage.getItem(storedAuthKey)
  if (!raw) return null
  const lastActivity = readLastActivity()
  if (lastActivity && Date.now() - lastActivity >= inactivityTimeoutMs) {
    sessionStorage.removeItem(storedAuthKey)
    sessionStorage.removeItem(storedActivityKey)
    return null
  }
  try {
    const parsed = JSON.parse(raw) as AuthCredentials
    if (parsed.username && parsed.password) {
      if (!lastActivity) {
        sessionStorage.setItem(storedActivityKey, Date.now().toString())
      }
      return parsed
    }
  } catch {
    sessionStorage.removeItem(storedAuthKey)
    sessionStorage.removeItem(storedActivityKey)
  }
  return null
}

function readLastActivity() {
  const timestamp = Number(sessionStorage.getItem(storedActivityKey))
  return Number.isFinite(timestamp) && timestamp > 0 ? timestamp : 0
}

function readInactivityTimeout() {
  const configured = Number(import.meta.env.VITE_INACTIVITY_TIMEOUT_MS)
  return Number.isFinite(configured) && configured > 0
    ? Math.max(configured, 60_000)
    : 180_000
}

function formatTimeout(timeoutMs: number) {
  const minutes = Math.round(timeoutMs / 60_000)
  return `${minutes} minute${minutes === 1 ? '' : 's'}`
}
