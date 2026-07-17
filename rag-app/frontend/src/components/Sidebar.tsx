import type { StatusResponse, UsageStats } from '../types'
import { CostTracker } from './CostTracker'
import { DocumentUpload } from './DocumentUpload'

interface SidebarProps {
  status: StatusResponse
  isUploading: boolean
  totalCost: number
  totalQuestions: number
  cacheHits: number
  lastUsage?: UsageStats
  onUpload: (file: File) => Promise<void>
  onClear: () => Promise<void>
}

export function Sidebar({
  status,
  isUploading,
  totalCost,
  totalQuestions,
  cacheHits,
  lastUsage,
  onUpload,
  onClear,
}: SidebarProps) {
  return (
    <aside className="flex h-full w-full flex-col border-r border-white/10 bg-ink-950 px-5 py-5 lg:w-[280px]">
      <div className="mb-7">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded bg-accent-500 text-sm font-black text-white">
            AR
          </div>
          <div>
            <h1 className="text-base font-semibold text-white">Adaptive RAG</h1>
            <p className="text-xs text-slate-500">Claude + Pinecone</p>
          </div>
        </div>
      </div>

      <DocumentUpload disabled={isUploading} onUpload={onUpload} />

      <section className="sidebar-section">
        <div className="section-label">Document</div>
        <div className="mt-3 rounded border border-white/10 bg-white/[0.03] p-3">
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs text-slate-400">Status</span>
            <span className={status.document_loaded ? 'status-pill-live' : 'status-pill-idle'}>
              {status.document_loaded ? 'Loaded' : 'Empty'}
            </span>
          </div>
          <p className="mt-3 break-words text-sm font-medium text-slate-100">
            {status.document_name || 'No document selected'}
          </p>
          <p className="mt-2 text-xs text-slate-500">{status.total_chunks} indexed chunks</p>
        </div>
      </section>

      <CostTracker
        totalCost={totalCost}
        totalQuestions={totalQuestions}
        cacheHits={cacheHits}
        lastUsage={lastUsage}
      />

      <button className="mt-auto clear-button" onClick={() => void onClear()}>
        Clear document
      </button>
    </aside>
  )
}
