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
}

export interface UploadResponse {
  filename: string
  chunks: number
  summary: string
}

export interface ChatResponse {
  answer: string
  sources: string[]
  usage: UsageStats
}

export interface StatusResponse {
  document_loaded: boolean
  document_name: string | null
  total_chunks: number
}
