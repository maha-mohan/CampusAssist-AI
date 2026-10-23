import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { Badge, Empty, ErrorNote, Loading, PageHeader, Pager, Panel, Table, inputCls, filterCls } from '../components/ui'
import { timeAgo } from '../lib/format'

const STATUS_TABS = [
  { value: 'open,in_progress', label: 'Active' },
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'resolved,closed', label: 'Resolved' },
  { value: '', label: 'All' },
]

export default function Tickets() {
  const [params, setParams] = useSearchParams()
  const status = params.get('status') ?? 'open,in_progress'
  const category = params.get('category') || ''
  const departmentId = params.get('department_id') || ''
  const [q, setQ] = useState(params.get('q') || '')
  const page = Number(params.get('page') || 1)

  const set = (k, v) => {
    const next = new URLSearchParams(params)
    if (v) next.set(k, v)
    else next.delete(k)
    if (k !== 'page') next.delete('page')
    if (k === 'status' && v === '') next.set('status', '')
    setParams(next)
  }

  const query = { status: status || undefined, category: category || undefined, department_id: departmentId || undefined, q: params.get('q') || undefined, page }
  const { data, isLoading, error } = useQuery({ queryKey: ['tickets', query], queryFn: () => api.tickets(query), placeholderData: keepPreviousData })
  const { data: categories } = useQuery({ queryKey: ['ticket-categories'], queryFn: api.ticketCategories })
  const { data: departments } = useQuery({ queryKey: ['departments'], queryFn: api.departments })

  return (
    <>
      <PageHeader title="Tickets" description="Requests students and parents raised from the chat. Each one is routed to a department by topic." />
      <Panel>
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3">
          <div className="flex flex-wrap gap-1" role="tablist" aria-label="Status">
            {STATUS_TABS.map((t) => (
              <button key={t.label} type="button" role="tab" aria-selected={status === t.value} onClick={() => set('status', t.value)}
                className={`rounded-md px-3 py-1.5 text-sm font-semibold ${status === t.value ? 'bg-navy text-white' : 'text-slate2 hover:bg-mist'}`}>
                {t.label}
              </button>
            ))}
          </div>
          <form className="ml-auto flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); set('q', q.trim()) }}>
            <select aria-label="Topic" value={category} onChange={(e) => set('category', e.target.value)} className={filterCls}>
              <option value="">All topics</option>
              {categories?.map((c) => <option key={c}>{c}</option>)}
            </select>
            <select aria-label="Department" value={departmentId} onChange={(e) => set('department_id', e.target.value)} className={filterCls}>
              <option value="">All departments</option>
              {departments?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ticket ID, name, email or phone" className={`${filterCls} w-64`} />
          </form>
        </div>
        {isLoading && <Loading />}
        <ErrorNote error={error} />
        {data && !data.items.length && <Empty title="No tickets here">When someone raises a ticket from the chat, it appears in this list.</Empty>}
        {data?.items.length > 0 && (
          <Table head={['Ticket', 'Subject', 'Topic', 'Department', 'Priority', 'Status', 'Raised']}>
            {data.items.map((t) => (
              <tr key={t.id} className="hover:bg-mist/60">
                <td className="whitespace-nowrap px-5 py-3"><Link to={`/tickets/${t.id}`} className="font-semibold text-navy underline-offset-2 hover:underline">{t.ticket_code}</Link></td>
                <td className="px-5 py-3"><p className="line-clamp-1 max-w-xs">{t.subject}</p><p className="text-[13px] text-slate2">{t.name}</p></td>
                <td className="whitespace-nowrap px-5 py-3">{t.category}</td>
                <td className="whitespace-nowrap px-5 py-3 text-slate2">{t.department?.name || '—'}</td>
                <td className="px-5 py-3">{t.priority !== 'normal' ? <Badge value={t.priority} /> : <span className="text-slate2">Normal</span>}</td>
                <td className="px-5 py-3"><Badge value={t.status} /></td>
                <td className="whitespace-nowrap px-5 py-3 text-slate2">{timeAgo(t.created_at)}</td>
              </tr>
            ))}
          </Table>
        )}
        {data && <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={(p) => set('page', String(p))} />}
      </Panel>
    </>
  )
}
