import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import { ErrorNote, Loading, PageHeader, Panel, Empty } from '../components/ui'
import { pct, timeAgo, titleCase } from '../lib/format'

export default function Overview() {
  const [days, setDays] = useState(14)
  const { data, isLoading, error } = useQuery({ queryKey: ['overview', days], queryFn: () => api.overview(days) })
  const { data: unanswered } = useQuery({ queryKey: ['unanswered', 'overview', days], queryFn: () => api.unanswered({ days, page_size: 8 }) })

  return (
    <>
      <PageHeader
        title="Overview"
        description="What students and parents asked, and where the assistant needs better information."
        actions={
          <select aria-label="Period" value={days} onChange={(e) => setDays(Number(e.target.value))}
            className="rounded-md border border-line bg-white px-3 py-2 text-sm">
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        }
      />
      {isLoading && <Loading />}
      <ErrorNote error={error} />
      {data && (
        <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
          {/* The most actionable thing on the page leads. */}
          <Panel
            title="Questions the assistant couldn't answer"
            action={<Link to="/attention" className="text-sm font-semibold text-navy underline underline-offset-2">See all</Link>}
          >
            {!unanswered?.items?.length ? (
              <Empty title="Nothing unanswered in this period">Every question found a match in the documents or FAQs.</Empty>
            ) : (
              <ol className="divide-y divide-line">
                {unanswered.items.map((u) => (
                  <li key={u.message_id} className="flex items-start justify-between gap-4 px-5 py-3">
                    <p className="text-[15px]">{u.question}</p>
                    <span className="shrink-0 text-[13px] text-slate2">{u.count > 1 ? `${u.count} times, last ` : ''}{timeAgo(u.created_at)}</span>
                  </li>
                ))}
              </ol>
            )}
            <p className="border-t border-line px-5 py-3 text-[13.5px] text-slate2">
              Add an FAQ or upload the right document for these, and the assistant will answer them next time.
            </p>
          </Panel>

          <div className="grid content-start gap-6">
            <Panel title="At a glance">
              <dl className="grid grid-cols-2 gap-x-6 gap-y-4 px-5 py-4">
                <Stat label="Conversations" value={data.sessions} note={`${data.sessions_today} today`} />
                <Stat label="Questions answered" value={pct(data.answer_rate)} note={`${data.answered} of ${data.questions}`} />
                <Stat label="Open tickets" value={data.open_tickets} note={<Link className="underline" to="/tickets">View tickets</Link>} />
                <Stat label="Helpful ratings" value={data.feedback.positive + data.feedback.negative ? pct(data.feedback.positive / (data.feedback.positive + data.feedback.negative)) : '—'} note={`${data.feedback.negative} marked not helpful`} />
                <Stat label="Avg. response" value={`${(data.avg_latency_ms / 1000).toFixed(1)} s`} />
                <Stat label="AI cost (est.)" value={`$${data.estimated_cost_usd.toFixed(2)}`} note={`${data.tokens.toLocaleString('en-IN')} tokens`} />
              </dl>
            </Panel>
            <Panel title="Knowledge base">
              <dl className="grid grid-cols-3 gap-4 px-5 py-4">
                <Stat label="Active documents" value={data.knowledge.documents_active} />
                <Stat label="Failed" value={data.knowledge.documents_failed} warn={data.knowledge.documents_failed > 0} />
                <Stat label="FAQs" value={data.knowledge.faqs_active} />
              </dl>
            </Panel>
          </div>

          <Panel title="Daily messages" className="lg:col-span-2">
            <div className="h-64 px-2 py-4">
              {data.daily.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.daily.map((d) => ({ ...d, answered: d.messages - d.unanswered, label: d.date.slice(5) }))}>
                    <CartesianGrid vertical={false} stroke="#dde1ec" />
                    <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={12} />
                    <YAxis allowDecimals={false} tickLine={false} axisLine={false} fontSize={12} width={32} />
                    <Tooltip cursor={{ fill: '#eef0f6' }} />
                    <Bar dataKey="answered" name="Answered" stackId="a" fill="#1f2a5c" />
                    <Bar dataKey="unanswered" name="Not answered" stackId="a" fill="#e7a21b" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <Empty title="No conversations yet">Once the widget is on the website, daily activity shows here.</Empty>
              )}
            </div>
          </Panel>

          <Panel title="Most asked">
            {data.top_questions.length ? (
              <ul className="divide-y divide-line">
                {data.top_questions.map((q) => (
                  <li key={q.question} className="flex justify-between gap-4 px-5 py-2.5 text-[14.5px]">
                    <span>{q.question}</span><span className="text-slate2">{q.count}</span>
                  </li>
                ))}
              </ul>
            ) : <Empty title="No questions yet" />}
          </Panel>

          <Panel title="Tickets by topic">
            {data.tickets_by_category.length ? (
              <ul className="divide-y divide-line">
                {data.tickets_by_category.map((c) => (
                  <li key={c.category} className="flex justify-between gap-4 px-5 py-2.5 text-[14.5px]">
                    <Link className="hover:underline" to={`/tickets?category=${encodeURIComponent(c.category)}`}>{titleCase(c.category)}</Link>
                    <span className="text-slate2">{c.count}</span>
                  </li>
                ))}
              </ul>
            ) : <Empty title="No tickets in this period" />}
          </Panel>
        </div>
      )}
    </>
  )
}

function Stat({ label, value, note, warn }) {
  return (
    <div>
      <dt className="text-[13px] text-slate2">{label}</dt>
      <dd className={`text-[24px] font-bold leading-tight ${warn ? 'text-danger' : 'text-navy-deep'}`}>{value}</dd>
      {note && <dd className="text-[12.5px] text-slate2">{note}</dd>}
    </div>
  )
}
