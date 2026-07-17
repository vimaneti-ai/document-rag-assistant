export interface UsageStats {
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
  cost_usd: number
  cache_hit: boolean
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  usage?: UsageStats
  sources?: string[]
  pipeline?: PipelineOperation
  questionVisualization?: QuestionVisualization
}

export interface UploadResponse {
  filename: string
  chunks: number
  summary: string
  pipeline: PipelineOperation
  visualization: IngestionVisualization
}

export interface ChatResponse {
  answer: string
  sources: string[]
  usage: UsageStats
  pipeline: PipelineOperation
  visualization: QuestionVisualization
}

export interface StatusResponse {
  document_loaded: boolean
  document_name: string | null
  total_chunks: number
}

export type PipelineKind = 'upload' | 'chat'
export type PipelineStatus = 'pending' | 'running' | 'completed' | 'failed'
export type PipelineStepStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface PipelineStep {
  id: string
  label: string
  status: PipelineStepStatus
  detail: string | null
  duration_ms: number | null
}

export interface PipelineOperation {
  operation_id: string
  kind: PipelineKind
  status: PipelineStatus
  started_at: number
  elapsed_ms: number
  steps: PipelineStep[]
}

export interface IngestionChunk {
  index: number
  start: number
  end: number
  characters: number
  overlap_with_previous: number
  embedding_preview: number[]
}

export interface IngestionVisualization {
  document_name: string
  character_count: number
  estimated_tokens: number
  total_chunks: number
  embedding_dimension: number
  index_name: string
  namespace: string
  chunks: IngestionChunk[]
}

export interface RetrievalMatch {
  rank: number
  source: string
  score: number
  characters: number
  excerpt: string
}

export interface QuestionVisualization {
  question: string
  query_embedding_preview: number[]
  embedding_dimension: number
  matches: RetrievalMatch[]
  retrieved_context_characters: number
  document_context_characters: number
  history_messages: number
  model: string
  answer_characters: number
  source_count: number
  cache_status: 'hit' | 'write' | 'none'
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
}
