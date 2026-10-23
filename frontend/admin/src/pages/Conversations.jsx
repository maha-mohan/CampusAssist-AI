import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { api } from '../api/client'
import { Badge, Empty, ErrorNote, Loading, PageHeader, Pager, Panel, inputCls, filterCls } from '../components/ui'
import { LANG, fmtDateTime, timeAgo } from '../lib/format'

export default function Conversations() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('')
  const list = useQuery({ queryKey: ['chats', page, q], queryFn: () => api.chats({ page, q: q || undefined }), placeholderData: keepPreviousData })
  const detail = useQuery({ queryKey: ['chat', id], queryFn: () => api.chat(id), enabled: !!id })

  return (
    <>
      <PageHeader title="Conversations" description="Read chats to see how the assistant answered. Visitors are anonymous; no names are stored unless they raise a ticket." />
      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        <Panel>
          <form className="border-b border-line p-3" onSubmit={(e) => { e.preventDefault(); setPage(1); setQ(search.trim()) }}>
            <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search messages" className={`${filterCls} w-full`} />
          </form>
          {list.isLoading && <Loading />}
          <ErrorNote error={list.error} />
          {list.data && !list.data.items.length && <Empty title="No conversations yet" />}
          <ul className="divide-y divide-line">
            {list.data?.items.map((s) => (
              <li key={s.id}>
                <button type="button" onClick={() => navigate(`/conversations/${s.id}`)}
                  className={`block w-full px-4 py-3 text-left hover:bg-mist ${id === s.id ? 'border-l-[3px] border-marigold bg-mist' : 'border-l-[3px] border-transparent'}`}>
                  <p className="line-clamp-1 text-[14.5px] font-semibold">{s.first_message || 'No messages'}</p>
                  <p className="mt-0.5 text-[12.5px] text-slate2">
                    {timeAgo(s.last_active_at)} · {Math.round(s.message_count / 2)} questions · {LANG[s.language] || s.language}
                    {s.unanswered > 0 && <span className="text-[#7a5200]"> · {s.unanswered} not answered</span>}
                  </p>
                </button>
              </li>
            ))}
          </ul>
          {list.data && <Pager page={list.data.page} pageSize={list.data.page_size} total={list.data.total} onPage={setPage} />}
        </Panel>

        <Panel title={id ? 'Transcript' : undefined}>
          {!id && <Empty title="Pick a conversation">Choose one on the left to read the full transcript.</Empty>}
          {detail.isLoading && <Loading />}
          <ErrorNote error={detail.error} />
          {detail.data && (
            <div className="px-5 py-4">
              <p className="mb-4 text-[13px] text-slate2">
                Started {fmtDateTime(detail.data.session.started_at)}
                {detail.data.session.page_url && <> on <span className="break-all">{detail.data.session.page_url}</span></>}
              </p>
              {detail.data.tickets.length > 0 && (
                <p className="mb-4 text-sm">Tickets: {detail.data.tickets.map((t) => <span key={t.ticket_code} className="mr-2"><strong>{t.ticket_code}</strong> <Badge value={t.status} /></span>)}</p>
              )}
              <ul className="space-y-4">
                {detail.data.messages.map((m) =>
                  m.role === 'user' ? (
                    <li key={m.id} className="text-right">
                      <span className="inline-block max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-navy px-4 py-2 text-left text-[14.5px] text-white">{m.content}</span>
                    </li>
                  ) : (
                    <li key={m.id} className={`border-l-[3px] pl-3 ${m.answered ? 'border-marigold' : 'border-line'}`}>
                      <p className="whitespace-pre-wrap text-[14.5px]">{m.content.replace(/\s?\[\d{1,2}\]/g, '')}</p>
                      <p className="mt-1 flex flex-wrap items-center gap-x-3 text-[12.5px] text-slate2">
                        <span>{m.answer_source === 'rag' ? 'From documents' : m.answer_source === 'faq' ? 'From FAQ' : m.answer_source === 'cache' ? 'Cached answer' : m.answer_source === 'fallback' ? 'Not answered' : 'Standard reply'}</span>
                        {m.confidence != null && <span>match {Math.round(m.confidence * 100)}%</span>}
                        {m.latency_ms > 0 && <span>{(m.latency_ms / 1000).toFixed(1)} s</span>}
                        {m.sources?.map((s, i) => s.document_id ? <Link key={i} to={`/documents?open=${s.document_id}`} className="underline">{s.title}</Link> : <span key={i}>{s.title}</span>)}
                        {m.rating === 1 && <ThumbsUp size={14} className="text-leaf" aria-label="Rated helpful" />}
                        {m.rating === -1 && <ThumbsDown size={14} className="text-danger" aria-label="Rated not helpful" />}
                      </p>
                    </li>
                  ),
                )}
              </ul>
            </div>
          )}
        </Panel>
      </div>
    </>
  )
}
