const IST = { timeZone: 'Asia/Kolkata' }

export const fmtDateTime = (v) =>
  v ? new Date(v).toLocaleString('en-IN', { ...IST, day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }) : '—'

export const fmtDate = (v) =>
  v ? new Date(v).toLocaleDateString('en-IN', { ...IST, day: 'numeric', month: 'short', year: 'numeric' }) : '—'

export function timeAgo(v) {
  if (!v) return '—'
  const s = Math.round((Date.now() - new Date(v).getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  if (s < 86400 * 7) return `${Math.floor(s / 86400)} d ago`
  return fmtDate(v)
}

export const titleCase = (s) => (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

export const LANG = { en: 'English', ta: 'Tamil', 'ta-en': 'Tanglish', hi: 'Hindi' }

export const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`)
