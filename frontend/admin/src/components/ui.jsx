// Small shared UI primitives. Plain, quiet, hairline-bordered — the content is the point.
import { X } from 'lucide-react'
import { useEffect } from 'react'

export function PageHeader({ title, description, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[26px] font-bold leading-tight text-navy-deep">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-[15px] text-slate2">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

export function Button({ variant = 'primary', className = '', ...props }) {
  const styles = {
    primary: 'bg-navy text-white hover:bg-navy-deep',
    accent: 'bg-marigold text-navy-deep hover:brightness-95',
    ghost: 'border border-line bg-white text-ink hover:bg-mist',
    danger: 'border border-line bg-white text-danger hover:bg-red-50',
    link: 'text-navy underline underline-offset-2 hover:text-navy-deep',
  }
  const pad = variant === 'link' ? 'p-0' : 'px-3.5 py-2'
  return (
    <button
      type="button"
      className={`inline-flex items-center gap-2 rounded-md text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${pad} ${styles[variant]} ${className}`}
      {...props}
    />
  )
}

export function Panel({ title, action, children, className = '' }) {
  return (
    <section className={`rounded-lg border border-line bg-white ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
          {title && <h2 className="text-[16px] font-bold text-navy-deep">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

const STATUS = {
  open: 'bg-marigold-soft text-[#7a5200]',
  in_progress: 'bg-navy-soft text-navy',
  resolved: 'bg-green-50 text-leaf',
  closed: 'bg-mist text-slate2',
  active: 'bg-green-50 text-leaf',
  pending: 'bg-mist text-slate2',
  processing: 'bg-navy-soft text-navy',
  failed: 'bg-red-50 text-danger',
  archived: 'bg-mist text-slate2',
  high: 'bg-red-50 text-danger',
  urgent: 'bg-red-100 text-danger',
  normal: 'bg-mist text-slate2',
  low: 'bg-mist text-slate2',
}

export function Badge({ value, children }) {
  return (
    <span className={`inline-block whitespace-nowrap rounded px-2 py-0.5 text-[12.5px] font-semibold ${STATUS[value] || 'bg-mist text-slate2'}`}>
      {children || (value || '').replace(/_/g, ' ')}
    </span>
  )
}

export function Field({ label, hint, error, children }) {
  return (
    <label className="grid gap-1 text-sm font-semibold text-ink">
      {label}
      {children}
      {hint && !error && <span className="text-[12.5px] font-normal text-slate2">{hint}</span>}
      {error && <span className="text-[12.5px] font-normal text-danger">{error}</span>}
    </label>
  )
}

const baseInput =
  'rounded-md border border-line bg-white px-3 py-2 text-[15px] font-normal text-ink placeholder:text-slate2/70 focus:border-navy focus:outline-none focus:ring-2 focus:ring-marigold/50'
export const inputCls = `w-full ${baseInput}`
// For toolbar filters: sized by content (or an explicit width class).
export const filterCls = `${baseInput} py-1.5 text-sm`

export function Modal({ title, onClose, children, wide = false }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-navy-deep/40 p-4 pt-[8vh]" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title} className={`w-full ${wide ? 'max-w-3xl' : 'max-w-lg'} rounded-lg border border-line bg-white shadow-xl`}>
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <h2 className="text-[17px] font-bold text-navy-deep">{title}</h2>
          <button type="button" aria-label="Close" onClick={onClose} className="rounded p-1 text-slate2 hover:bg-mist"><X size={18} /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}

export function Empty({ title, children }) {
  return (
    <div className="px-5 py-10 text-center">
      <p className="font-semibold text-ink">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-md text-sm text-slate2">{children}</div>}
    </div>
  )
}

export function Pager({ page, pageSize, total, onPage }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  if (pages <= 1) return null
  return (
    <div className="flex items-center justify-between border-t border-line px-5 py-3 text-sm text-slate2">
      <span>{total} total</span>
      <div className="flex items-center gap-2">
        <Button variant="ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</Button>
        <span>Page {page} of {pages}</span>
        <Button variant="ghost" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</Button>
      </div>
    </div>
  )
}

export function Loading() {
  return <p className="px-5 py-8 text-sm text-slate2">Loading…</p>
}

export function ErrorNote({ error }) {
  if (!error) return null
  return <p role="alert" className="px-5 py-4 text-sm text-danger">{error.message || String(error)}</p>
}

export function Table({ head, children }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-[14.5px]">
        <thead>
          <tr className="border-b border-line text-[13px] text-slate2">
            {head.map((h) => <th key={h} className="whitespace-nowrap px-5 py-2.5 font-semibold">{h}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  )
}
