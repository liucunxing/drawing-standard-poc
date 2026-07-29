import dayjs from 'dayjs'

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = dayjs(value)
  return date.isValid() ? date.format('YYYY-MM-DD HH:mm:ss') : '—'
}

export function formatFileSize(bytes: number | null | undefined): string {
  const value = Number(bytes || 0)
  if (!Number.isFinite(value) || value <= 0) return '—'
  if (value < 1024) return `${value} B`
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 ** 2).toFixed(1)} MB`
}

export function formatPercent(value: number | null | undefined): number {
  const parsed = Number(value || 0)
  return Math.max(0, Math.min(100, Number.isFinite(parsed) ? Math.round(parsed) : 0))
}
