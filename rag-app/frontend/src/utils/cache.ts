import type { UsageStats } from '../types'

export type CacheStatus = 'hit' | 'written' | 'not-cached'

export function getCacheStatus(usage: UsageStats): CacheStatus {
  if (usage.cache_read_tokens > 0) return 'hit'
  if (usage.cache_write_tokens > 0) return 'written'
  return 'not-cached'
}

export function getCacheLabel(status: CacheStatus) {
  if (status === 'hit') return 'Cache hit'
  if (status === 'written') return 'Cache written'
  return 'Not cached'
}
