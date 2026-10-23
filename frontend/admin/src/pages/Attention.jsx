import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { can, useAuth } from '../store/auth'
import FaqForm from '../components/FaqForm'
import { Button, Empty, ErrorNote, Loading, Modal, PageHeader, Pager, Panel } from '../components/ui'
import { timeAgo } from '../lib/format'

export default function Attention() {
  const user = useAuth((s) => s.user)
  const [tab, setTab] = useState('unanswered')
  const [page, setPage] = useState(1)
  const [faqFor, setFaqFor] = useState(null)

  const unanswered = useQuery({ queryKey: ['unanswered', page], queryFn: () => api.unanswered({ days: 90, page }), enabled: tab === 'unanswered' })
  const negative = useQuery({ queryKey: ['negative', page], queryFn: () => api.negativeFeedback({ page }), enabled: tab === 'negative' })
  const q = tab === 'unanswered' ? unanswered : negative

  const switchTab = (t) => { setTab(t); setPage(1) }

  return (
    <>
      <PageHeader
        title="Needs attention"
        description="Questions the assistant couldn't answer, and answers people marked as not helpful. Fixing these is the fastest way to improve the bot."
      />
      <Panel>
        <div className="flex gap-1 border-b border-line px-5 py-3" role="tablist">
          {[['unanswered', 'Not answered (90 days)'], ['negative', 'Marked not helpful']].map(([v, l]) => (
            <button key={v} type="button" role="tab" aria-selected={tab === v} onClick={() => switchTab(v)}
              className={`rounded-md px-3 py-1.5 text-sm font-semibold ${tab === v ? 'bg-navy text-white' : 'text-slate2 hover:bg-mist'}`}>{l}</button>
          ))}
        </div>
        {q.isLoading && <Loading />}
        <ErrorNote error={q.error} />
        {q.data && !q.data.items.length && (
          <Empty title={tab === 'unanswered' ? 'No unanswered questions' : 'No negative feedback'}>
            {tab === 'unanswered' ? 'The knowledge base covered everything people asked.' : 'Nobody has marked an answer as not helpful.'}
          </Empty>
        )}
        <ul className="divide-y divide-line">
          {q.data?.items.map((it) => (
            <li key={it.message_id} className="px-5 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <p className="text-[15.5px] font-semibold">{it.question || '(question not available)'}</p>
                <span className="text-[13px] text-slate2">{it.count > 1 ? `Asked ${it.count} times, last ` : ''}{timeAgo(it.created_at)}</span>
              </div>
              {tab === 'negative' && (
                <>
                  <p className="mt-2 border-l-[3px] border-line pl-3 text-[14px] text-slate2 line-clamp-3">{it.answer.replace(/\s?\[\d{1,2}\]/g, '')}</p>
                  {it.comment && <p className="mt-2 text-[14px]">Comment: “{it.comment}”</p>}
                </>
              )}
              <div className="mt-2 flex flex-wrap gap-4">
                {can(user, 'manageContent') && (
                  <Button variant="link" onClick={() => setFaqFor(it.question || '')}>Answer with an FAQ</Button>
                )}
                <Link to={`/conversations/${it.session_id}`} className="text-sm font-semibold text-navy underline underline-offset-2">Open conversation</Link>
              </div>
            </li>
          ))}
        </ul>
        {q.data && <Pager page={q.data.page} pageSize={q.data.page_size} total={q.data.total} onPage={setPage} />}
      </Panel>

      {faqFor !== null && (
        <Modal title="Add an FAQ" onClose={() => setFaqFor(null)}>
          <FaqForm initialQuestion={faqFor} onDone={() => setFaqFor(null)} />
        </Modal>
      )}
    </>
  )
}
