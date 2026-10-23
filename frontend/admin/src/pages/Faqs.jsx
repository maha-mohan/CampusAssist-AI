import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Plus } from 'lucide-react'
import { api } from '../api/client'
import { can, useAuth } from '../store/auth'
import FaqForm from '../components/FaqForm'
import { Badge, Button, Empty, ErrorNote, Loading, Modal, PageHeader, Panel, inputCls, filterCls } from '../components/ui'

export default function Faqs() {
  const user = useAuth((s) => s.user)
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [editing, setEditing] = useState(null) // null | 'new' | faq
  const { data, isLoading, error } = useQuery({ queryKey: ['faqs', q], queryFn: () => api.faqs({ q: q || undefined }) })
  const del = useMutation({
    mutationFn: (id) => api.deleteFaq(id),
    onSuccess: () => { toast.success('FAQ deleted'); qc.invalidateQueries({ queryKey: ['faqs'] }) },
    onError: (e) => toast.error(e.message),
  })
  const editable = can(user, 'manageContent')

  return (
    <>
      <PageHeader
        title="FAQs"
        description="Verified answers for common questions. When a question closely matches an FAQ, the assistant gives this answer word for word."
        actions={editable && <Button onClick={() => setEditing('new')}><Plus size={16} /> Add FAQ</Button>}
      />
      <Panel>
        <div className="border-b border-line px-5 py-3">
          <input type="search" placeholder="Search FAQs" value={q} onChange={(e) => setQ(e.target.value)} className={`${filterCls} w-full max-w-sm`} />
        </div>
        {isLoading && <Loading />}
        <ErrorNote error={error} />
        {data && !data.length && <Empty title="No FAQs yet">Start with the questions the office phone gets most: timings, location, contact numbers.</Empty>}
        <ul className="divide-y divide-line">
          {data?.map((f) => (
            <li key={f.id} className="px-5 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <p className="text-[15.5px] font-semibold">{f.question}</p>
                <div className="flex items-center gap-3 text-sm">
                  {!f.is_active && <Badge value="archived">Not in use</Badge>}
                  <span className="text-slate2">Used {f.hits}×</span>
                  {editable && <Button variant="link" onClick={() => setEditing(f)}>Edit</Button>}
                  {editable && <Button variant="link" className="!text-danger" onClick={() => window.confirm('Delete this FAQ?') && del.mutate(f.id)}>Delete</Button>}
                </div>
              </div>
              <p className="mt-1 max-w-3xl whitespace-pre-wrap text-[14.5px] text-slate2">{f.answer}</p>
            </li>
          ))}
        </ul>
      </Panel>
      {editing && (
        <Modal title={editing === 'new' ? 'Add FAQ' : 'Edit FAQ'} onClose={() => setEditing(null)}>
          <FaqForm faq={editing === 'new' ? null : editing} onDone={() => setEditing(null)} />
        </Modal>
      )}
    </>
  )
}
