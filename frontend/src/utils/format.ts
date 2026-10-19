import type { TokenUsage } from '@/types'

/** Format a token count compactly, e.g. 1290 -> "1.3k". */
export function formatTokens(value: number | null | undefined): string {
  if (value == null) return '–'
  if (value < 1000) return String(value)
  if (value < 1_000_000) return `${(value / 1000).toFixed(value < 10_000 ? 1 : 0)}k`
  return `${(value / 1_000_000).toFixed(1)}M`
}

/** Format an amount in an ISO 4217 currency; small amounts keep more decimals. */
export function formatMoney(amount: number, currency: string): string {
  const digits = amount !== 0 && Math.abs(amount) < 0.01 ? 4 : Math.abs(amount) < 1 ? 3 : 2
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(amount)
  } catch (_e) {
    return `${amount.toFixed(digits)} ${currency}`
  }
}

/** Format the cost computed from configured model prices (``null`` when no prices are set). */
export function formatCost(usage: Pick<TokenUsage, 'cost' | 'currency'> | null | undefined): string | null {
  if (!usage || usage.cost == null || !usage.currency || usage.currency === 'mixed') return null
  return formatMoney(usage.cost, usage.currency)
}

/** One-line usage summary, e.g. "1.3k tokens · $0.040". Tokens only when no prices are set. */
export function formatUsage(usage: TokenUsage | null | undefined): string | null {
  if (!usage) return null
  const parts: string[] = []
  if (usage.total_tokens) parts.push(`${formatTokens(usage.total_tokens)} tokens`)
  const cost = formatCost(usage)
  if (cost) parts.push(cost)
  return parts.length ? parts.join(' · ') : null
}

/** Detailed tooltip text for a usage object. */
export function describeUsage(usage: TokenUsage | null | undefined): string {
  if (!usage) return ''
  const lines = [
    `Input tokens: ${usage.input_tokens ?? '–'}`,
    `Output tokens: ${usage.output_tokens ?? '–'}`,
    `Total tokens: ${usage.total_tokens ?? '–'}`,
  ]
  const cost = formatCost(usage)
  if (cost) lines.push(`Cost: ${cost} (from configured model prices)`)
  if (usage.currency === 'mixed') lines.push('Cost: not summed (different currencies)')
  return lines.join('\n')
}

/** Format seconds as "8.4s" or "1m 12s". */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return ''
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`
  const minutes = Math.floor(seconds / 60)
  const rest = Math.round(seconds % 60)
  return `${minutes}m ${rest}s`
}

/** Time of day for today's items, otherwise a short date + time. */
export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return ''
  const date = new Date(value)
  const now = new Date()
  const sameDay = date.toDateString() === now.toDateString()
  const time = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  return sameDay ? time : `${date.toLocaleDateString('en-US', { day: '2-digit', month: 'short' })} ${time}`
}
