import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { ArrowLeft, Mail, Phone } from 'lucide-react'
import { api } from '../api/client'
import { can, useAuth } from '../store/auth'
import { Badge, Button, ErrorNote, Field, Loading, Panel, inputCls } from '../components/ui'
import { fmtDateTime, titleCase } from '../lib/format'

export default function TicketDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const user = useAuth((s) => s.user)
  const { data, isLoading, error } = useQuery({ queryKey: ['ticket', id], queryFn: () => api.ticket(id) })
  const { data: users } = useQuery({ queryKey: ['users'], queryFn: api.users, enabled: can(user, 'manageUsers') })
  const { data: departments } = useQuery({ queryKey: ['departments'], queryFn: api.departments })

  const ticket = data?.ticket
  const [form, setForm] = useState({ status: '', priority: '', department_id: '', assigned_to: '', note: '', is_public: true })
  useEffect(() => {
    if (ticket) setForm((f) => ({ ...f, status: ticket.status, priority: ticket.priority, department_id: ticket.department_id || '', assigned_to: ticket.assigned_to || '' }))
  }, [ticket])

  const save = useMutation({
    mutationFn: (body) => api.updateTicket(id, body),
    onSuccess: () => {
      toast.success('Ticket updated')
      setForm((f) => ({ ...f, note: '' }))
      qc.invalidateQueries({ queryKey: ['ticket', id] })
      qc.invalidateQueries({ queryKey: ['tickets'] })
      qc.invalidateQueries({ queryKey: ['overview'] })
    },
    onError: (e) => toast.error(e.message),
  })

  if (isLoading) return <Loading />
  if (error) return <ErrorNote error={error} />

  const submit = (e) => {
    e.preventDefault()
    const body = { note: form.note || null, is_public: form.is_public }
    if (form.status !== ticket.status) body.status = form.status
    if (form.priority !== ticket.priority) body.priority = form.priority
    if (can(user, 'moveTickets') && String(form.department_id) !== String(ticket.department_id || '')) body.department_id = form.department_id ? Number(form.department_id) : null
    if (String(form.assigned_to) !== String(ticket.assigned_to || '')) body.assigned_to = form.assigned_to ? Number(form.assigned_to) : null
    save.mutate(body)
  }

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  return (
    <>
      <Link to="/tickets" className="mb-4 inline-flex items-center gap-1 text-sm font-semibold text-navy hover:underline"><ArrowLeft size={16} /> All tickets</Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate2">{ticket.ticket_code} · raised {fmtDateTime(ticket.created_at)}</p>
          <h1 className="text-[26px] font-bold leading-tight text-navy-deep">{ticket.subject}</h1>
        </div>
        <div className="flex gap-2">{ticket.priority !== 'normal' && <Badge value={ticket.priority} />}<Badge value={ticket.status} /></div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="grid content-start gap-6">
          <Panel title="Request">
            <div className="px-5 py-4">
              <p className="whitespace-pre-wrap text-[15px] leading-relaxed">{ticket.description}</p>
              <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate2">
                <span className="font-semibold text-ink">{ticket.name}</span>
                {ticket.email && <a className="inline-flex items-center gap-1 hover:underline" href={`mailto:${ticket.email}?subject=${encodeURIComponent(`Re: ${ticket.ticket_code} ${ticket.subject}`)}`}><Mail size={14} />{ticket.email}</a>}
                {ticket.phone && <a className="inline-flex items-center gap-1 hover:underline" href={`tel:${ticket.phone}`}><Phone size={14} />{ticket.phone}</a>}
                <span>{ticket.category} → {ticket.department?.name || 'Unassigned'}</span>
              </div>
            </div>
          </Panel>

          <Panel title="History">
            <ol className="divide-y divide-line">
              {ticket.updates.map((u) => (
                <li key={u.id} className="px-5 py-3 text-[14.5px]">
                  <p className="text-[13px] text-slate2">
                    {fmtDateTime(u.created_at)} · {u.user?.name || 'System'}
                    {u.status_to && <> · status → <strong className="text-ink">{titleCase(u.status_to)}</strong></>}
                    {!u.is_public && <> · internal note</>}
                  </p>
                  {u.note && <p className="mt-0.5 whitespace-pre-wrap">{u.note}</p>}
                </li>
              ))}
            </ol>
          </Panel>

          {data.transcript.length > 0 && (
            <Panel title="Chat before the ticket">
              <ul className="max-h-96 space-y-3 overflow-y-auto px-5 py-4">
                {data.transcript.map((m, i) => (
                  <li key={i} className={m.role === 'user' ? 'text-right' : ''}>
                    <span className={`inline-block max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-left text-[14px] ${m.role === 'user' ? 'bg-navy text-white' : 'border-l-[3px] border-marigold bg-white'}`}>
                      {m.content.replace(/\s?\[\d{1,2}\]/g, '')}
                    </span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </div>

        <Panel title="Update ticket" className="h-fit lg:sticky lg:top-6">
          <form onSubmit={submit} className="grid gap-4 px-5 py-4">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Status">
                <select className={inputCls} value={form.status} onChange={set('status')}>
                  {['open', 'in_progress', 'resolved', 'closed'].map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
                </select>
              </Field>
              <Field label="Priority">
                <select className={inputCls} value={form.priority} onChange={set('priority')}>
                  {['low', 'normal', 'high', 'urgent'].map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
                </select>
              </Field>
            </div>
            {can(user, 'moveTickets') && (
              <Field label="Department">
                <select className={inputCls} value={form.department_id} onChange={set('department_id')}>
                  <option value="">Unassigned</option>
                  {departments?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </Field>
            )}
            {users && (
              <Field label="Assigned to">
                <select className={inputCls} value={form.assigned_to} onChange={set('assigned_to')}>
                  <option value="">Nobody</option>
                  {users.filter((u) => u.is_active).map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
                </select>
              </Field>
            )}
            <Field label="Note" hint={form.is_public ? 'The student sees this note and gets it by email.' : 'Only staff can see this note.'}>
              <textarea rows={4} className={inputCls} value={form.note} onChange={set('note')} placeholder="What was done, or what the student should do next" />
            </Field>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.is_public} onChange={set('is_public')} className="h-4 w-4 accent-[#1f2a5c]" />
              Share this note with the student
            </label>
            <Button type="submit" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save update'}</Button>
          </form>
        </Panel>
      </div>
    </>
  )
}
