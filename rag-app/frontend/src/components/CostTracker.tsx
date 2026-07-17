import type { UsageStats } from '../types'
import { getCacheLabel, getCacheStatus } from '../utils/cache'

interface CostTrackerProps {
  totalCost: number
  totalQuestions: number
  cacheHits: number
  lastUsage?: UsageStats
}

export function CostTracker({ totalCost, totalQuestions, cacheHits, lastUsage }: CostTrackerProps) {
  const cacheRate = totalQuestions ? Math.round((cacheHits / totalQuestions) * 100) : 0
  const cacheStatus = lastUsage ? getCacheStatus(lastUsage) : null

  return (
    <section className="sidebar-section">
      <div className="section-label">Session cost</div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <Metric label="Total" value={`$${totalCost.toFixed(5)}`} />
        <Metric label="Cache rate" value={`${cacheRate}%`} />
      </div>
      <div className="mt-3 rounded border border-white/10 bg-white/[0.03] p-3">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>Last request</span>
          <span className={cacheStatus === 'hit' ? 'text-emerald-300' : 'text-amber-300'}>
            {cacheStatus ? getCacheLabel(cacheStatus) : 'Waiting'}
          </span>
        </div>
        <div className="mt-2 text-xs leading-5 text-slate-300">
          {lastUsage
            ? `${lastUsage.input_tokens} in / ${lastUsage.output_tokens} out / ${lastUsage.cache_read_tokens} reused / ${lastUsage.cache_write_tokens} cached`
            : 'Ask a question to see token usage.'}
        </div>
      </div>
    </section>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.04] p-3">
      <div className="text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-slate-100">{value}</div>
    </div>
  )
}
