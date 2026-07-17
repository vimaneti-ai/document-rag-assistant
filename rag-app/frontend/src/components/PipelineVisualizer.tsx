import { useEffect, useState } from 'react'
import type {
  IngestionVisualization,
  PipelineKind,
  PipelineOperation,
  PipelineStatus,
  PipelineStep,
  QuestionVisualization,
} from '../types'

const blueprints: Record<PipelineKind, Array<Pick<PipelineStep, 'id' | 'label'>>> = {
  upload: [
    { id: 'validation', label: 'Validate file' },
    { id: 'parsing', label: 'Extract content' },
    { id: 'chunking', label: 'Create chunks' },
    { id: 'embedding', label: 'Generate embeddings' },
    { id: 'indexing', label: 'Store in Pinecone' },
    { id: 'summary', label: 'Create summary' },
  ],
  chat: [
    { id: 'query_embedding', label: 'Embed question' },
    { id: 'retrieval', label: 'Search Pinecone' },
    { id: 'prompt', label: 'Assemble context' },
    { id: 'generation', label: 'Generate with Claude' },
    { id: 'citations', label: 'Attach sources' },
  ],
}

export function createPendingOperation(
  operationId: string,
  kind: PipelineKind,
): PipelineOperation {
  return {
    operation_id: operationId,
    kind,
    status: 'pending',
    started_at: Date.now() / 1000,
    elapsed_ms: 0,
    steps: blueprints[kind].map((step) => ({
      ...step,
      status: 'pending',
      detail: null,
      duration_ms: null,
    })),
  }
}

export function PipelineVisualizer({
  operation,
  uploadOperation,
  ingestionVisualization,
}: {
  operation: PipelineOperation | null
  uploadOperation: PipelineOperation | null
  ingestionVisualization: IngestionVisualization | null
}) {
  const [selectedKind, setSelectedKind] = useState<PipelineKind>(operation?.kind || 'upload')

  useEffect(() => {
    if (operation) setSelectedKind(operation.kind)
  }, [operation?.operation_id])

  const visibleOperation =
    operation?.kind === selectedKind
      ? operation
      : selectedKind === 'upload' && uploadOperation
        ? uploadOperation
        : createPendingOperation(`preview-${selectedKind}`, selectedKind)
  const isPreview = visibleOperation.operation_id.startsWith('preview-')

  return (
    <section className="pipeline-band" aria-label="RAG pipeline activity">
      <div className="pipeline-heading">
        <div>
          <div className="section-label">Execution trace</div>
          <div className="mt-1 flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-100">RAG pipeline</h2>
            <StatusBadge status={isPreview ? 'pending' : visibleOperation.status} />
          </div>
        </div>
        <div className="flex items-center gap-3">
          {!isPreview && (
            <span className="text-xs tabular-nums text-slate-500">
              {formatDuration(visibleOperation.elapsed_ms)}
            </span>
          )}
          <div className="pipeline-tabs" aria-label="Pipeline view">
            <button
              className={selectedKind === 'upload' ? 'pipeline-tab-active' : 'pipeline-tab'}
              type="button"
              onClick={() => setSelectedKind('upload')}
            >
              Upload
            </button>
            <button
              className={selectedKind === 'chat' ? 'pipeline-tab-active' : 'pipeline-tab'}
              type="button"
              onClick={() => setSelectedKind('chat')}
            >
              Question
            </button>
          </div>
        </div>
      </div>

      <div className="pipeline-scroll">
        <div
          className="pipeline-track"
          style={{ gridTemplateColumns: `repeat(${visibleOperation.steps.length}, minmax(150px, 1fr))` }}
        >
          {visibleOperation.steps.map((step, index) => (
            <div className={`pipeline-stage pipeline-stage-${step.status}`} key={step.id}>
              <div className="pipeline-stage-top">
                <span className="pipeline-step-number">{index + 1}</span>
                <span className="pipeline-step-state">{stepStatusLabel(step.status)}</span>
              </div>
              <div className="mt-3 text-xs font-semibold text-slate-200">{step.label}</div>
              <div className="pipeline-detail">
                {step.detail || defaultDetail(selectedKind, step.id)}
              </div>
              <div className="pipeline-duration">
                {step.duration_ms === null ? 'Waiting' : formatDuration(step.duration_ms)}
              </div>
            </div>
          ))}
        </div>
      </div>
      {ingestionVisualization && (
        <IngestionFlow visualization={ingestionVisualization} />
      )}
    </section>
  )
}

export function QuestionFlow({
  visualization,
}: {
  visualization: QuestionVisualization
}) {
  return (
    <div className="question-flow">
      <div className="ingestion-flow-header">
        <div>
          <div className="section-label">Question transformation</div>
          <p>Actual query vector, Pinecone matches, prompt context, and Claude usage</p>
        </div>
        <span>{visualization.matches.length} retrieved matches</span>
      </div>

      <div className="question-flow-canvas">
        <div className="question-node">
          <small>Question</small>
          <strong>{visualization.question}</strong>
        </div>
        <div className="flow-arrow-down" aria-hidden="true" />
        <div className="query-vector-node">
          <small>Query embedding</small>
          <strong>
            [{visualization.query_embedding_preview.map(formatVectorValue).join(', ')}, ...]
          </strong>
          <span>{visualization.embedding_dimension} dimensions</span>
        </div>
        <div className="flow-arrow-down" aria-hidden="true" />

        <div className="retrieval-label">
          <strong>Pinecone semantic search</strong>
          <span>Ranked by cosine similarity</span>
        </div>
        <div className="retrieval-grid">
          {visualization.matches.map((match) => (
            <article className="retrieval-match" key={`${match.rank}-${match.source}`}>
              <div className="retrieval-match-heading">
                <span>#{match.rank}</span>
                <strong>{formatScore(match.score)}</strong>
              </div>
              <div className="similarity-track">
                <span style={{ width: `${scorePercentage(match.score)}%` }} />
              </div>
              <p>{match.excerpt}</p>
              <small>{match.source}</small>
            </article>
          ))}
        </div>

        <div className="flow-arrow-down" aria-hidden="true" />
        <div className="prompt-node">
          <div>
            <small>Retrieved context</small>
            <strong>{visualization.retrieved_context_characters.toLocaleString()} chars</strong>
          </div>
          <span>+</span>
          <div>
            <small>Cached document</small>
            <strong>{visualization.document_context_characters.toLocaleString()} chars</strong>
          </div>
          <span>+</span>
          <div>
            <small>Conversation</small>
            <strong>{visualization.history_messages} messages</strong>
          </div>
        </div>
        <div className="flow-arrow-down" aria-hidden="true" />

        <div className="generation-row">
          <div className="claude-node">
            <small>Generation model</small>
            <strong>{visualization.model}</strong>
            <span>
              {visualization.input_tokens.toLocaleString()} input
              {' / '}
              {visualization.output_tokens.toLocaleString()} output
            </span>
          </div>
          <div className={`cache-node cache-node-${visualization.cache_status}`}>
            <small>Prompt cache</small>
            <strong>{cacheStatusLabel(visualization.cache_status)}</strong>
            <span>
              {visualization.cache_status === 'hit'
                ? `${visualization.cache_read_tokens.toLocaleString()} tokens reused`
                : visualization.cache_status === 'write'
                  ? `${visualization.cache_write_tokens.toLocaleString()} tokens written`
                  : 'No cache tokens reported'}
            </span>
          </div>
        </div>
        <div className="flow-arrow-down" aria-hidden="true" />
        <div className="answer-node">
          <strong>Grounded answer</strong>
          <span>
            {visualization.answer_characters.toLocaleString()} characters
            {' / '}
            {visualization.source_count} source citations
          </span>
        </div>
      </div>
    </div>
  )
}

function IngestionFlow({
  visualization,
}: {
  visualization: IngestionVisualization
}) {
  return (
    <div className="ingestion-flow">
      <div className="ingestion-flow-header">
        <div>
          <div className="section-label">Document transformation</div>
          <p>Actual chunk ranges and embedding samples from the latest upload</p>
        </div>
        <span>
          Showing {visualization.chunks.length} of {visualization.total_chunks} chunks
        </span>
      </div>

      <div className="flow-canvas">
        <div className="flow-document-node">
          <strong>{visualization.document_name}</strong>
          <span>
            {visualization.character_count.toLocaleString()} characters
            {' / '}
            ~{visualization.estimated_tokens.toLocaleString()} tokens
          </span>
        </div>
        <div className="flow-arrow-down" aria-hidden="true" />

        <div
          className="flow-branches"
          style={{
            gridTemplateColumns: `repeat(${visualization.chunks.length}, minmax(190px, 1fr))`,
          }}
        >
          {visualization.chunks.map((chunk) => (
            <div className="flow-branch" key={chunk.index}>
              <div className="flow-chunk-node">
                {chunk.overlap_with_previous > 0 && (
                  <span className="flow-overlap-band">
                    {chunk.overlap_with_previous} overlap
                  </span>
                )}
                <strong>Chunk {chunk.index}</strong>
                <span>
                  characters {chunk.start.toLocaleString()}-{chunk.end.toLocaleString()}
                </span>
                <small>{chunk.characters.toLocaleString()} characters</small>
              </div>
              <div className="flow-arrow-down flow-arrow-short" aria-hidden="true" />
              <div className="flow-embedding-node">
                <strong>Embedding {chunk.index}</strong>
                <span>
                  [{chunk.embedding_preview.map(formatVectorValue).join(', ')}, ...]
                </span>
                <small>{visualization.embedding_dimension} dimensions</small>
              </div>
            </div>
          ))}
        </div>

        <div
          className="flow-merge"
          aria-hidden="true"
          style={{
            gridTemplateColumns: `repeat(${visualization.chunks.length}, 1fr)`,
          }}
        >
          {visualization.chunks.map((chunk) => (
            <span key={chunk.index} />
          ))}
        </div>
        <div className="flow-database-node">
          <strong>Pinecone vector database</strong>
          <span>{visualization.index_name}</span>
          <small>namespace: {visualization.namespace}</small>
        </div>
        <div className="flow-legend">
          <span className="flow-legend-swatch" />
          Amber bands show characters shared with the preceding chunk
        </div>
      </div>
    </div>
  )
}

export function PipelineTrace({ operation }: { operation: PipelineOperation }) {
  return (
    <details className="pipeline-trace">
      <summary>
        Execution trace
        <span>{formatDuration(operation.elapsed_ms)}</span>
      </summary>
      <ol>
        {operation.steps.map((step) => (
          <li key={step.id}>
            <span className={`trace-dot trace-dot-${step.status}`} />
            <span className="font-medium text-slate-300">{step.label}</span>
            <span className="trace-detail">{step.detail}</span>
            <span className="ml-auto tabular-nums text-slate-500">
              {step.duration_ms === null ? '-' : formatDuration(step.duration_ms)}
            </span>
          </li>
        ))}
      </ol>
    </details>
  )
}

function StatusBadge({ status }: { status: PipelineStatus }) {
  const labels: Record<PipelineStatus, string> = {
    pending: 'Overview',
    running: 'Live',
    completed: 'Complete',
    failed: 'Failed',
  }
  return <span className={`pipeline-status pipeline-status-${status}`}>{labels[status]}</span>
}

function stepStatusLabel(status: PipelineStep['status']) {
  const labels = {
    pending: 'Queued',
    running: 'Running',
    completed: 'Done',
    failed: 'Failed',
  }
  return labels[status]
}

function defaultDetail(kind: PipelineKind, stepId: string) {
  const details: Record<string, string> = {
    validation: 'Type and size checks',
    parsing: 'PDF, DOCX, text, CSV, or Markdown',
    chunking: '1,000 characters with overlap',
    embedding: 'MiniLM, 384 dimensions',
    indexing: 'Persistent vector namespace',
    summary: 'Claude document overview',
    query_embedding: 'MiniLM query vector',
    retrieval: 'Top four semantic matches',
    prompt: 'Context, history, and instructions',
    generation: 'Claude Haiku 4.5 with caching',
    citations: 'Source pages and chunks',
  }
  return details[stepId] || `${kind} processing`
}

function formatDuration(milliseconds: number) {
  if (milliseconds < 1000) return `${milliseconds} ms`
  return `${(milliseconds / 1000).toFixed(milliseconds < 10000 ? 1 : 0)} s`
}

function formatVectorValue(value: number) {
  return value.toFixed(2)
}

function formatScore(score: number) {
  return score.toFixed(3)
}

function scorePercentage(score: number) {
  return Math.max(3, Math.min(100, score * 100))
}

function cacheStatusLabel(status: QuestionVisualization['cache_status']) {
  if (status === 'hit') return 'Cache hit'
  if (status === 'write') return 'Cache written'
  return 'No cache event'
}
