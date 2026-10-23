import { useEffect, useState } from 'react'

const FALLBACK_CATEGORIES = ['Admission', 'Examination', 'Fees', 'Scholarship', 'Hostel', 'Transport', 'Placements', 'Academics', 'Library', 'Certificates', 'Technical', 'Other']

export default function TicketForm({ api, sessionId, prefill, onCreated, onCancel }) {
  const [categories, setCategories] = useState(FALLBACK_CATEGORIES)
  const [form, setForm] = useState({
    name: '',
    email: '',
    phone: '',
    category: prefill?.category || 'Other',
    subject: prefill?.subject || '',
    description: prefill?.description || '',
  })
  const [error, setError] = useState(null)
  const [sending, setSending] = useState(false)

  useEffect(() => {
    api.categories().then(setCategories).catch(() => {})
  }, [api])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setError(null)
    if (!form.email && !form.phone) {
      setError('Add an email or phone number so the department can reply to you.')
      return
    }
    setSending(true)
    try {
      const payload = { ...form, session_id: sessionId }
      if (!payload.email) delete payload.email
      if (!payload.phone) delete payload.phone
      const ticket = await api.createTicket(payload)
      onCreated(ticket)
    } catch (err) {
      setError(err.message.replace(/^body\.\w+: /, ''))
    } finally {
      setSending(false)
    }
  }

  return (
    <form className="hd-form" onSubmit={submit} aria-label="Raise a support ticket">
      <p className="hd-form-title">Raise a support ticket</p>
      <p className="hd-muted">The right department gets this and replies by email or phone.</p>

      <label>
        Your name
        <input required minLength={2} value={form.name} onChange={set('name')} autoComplete="name" />
      </label>
      <div className="hd-form-2">
        <label>
          Email
          <input type="email" value={form.email} onChange={set('email')} autoComplete="email" />
        </label>
        <label>
          Phone
          <input type="tel" inputMode="tel" pattern="\+?[0-9 \-]{8,15}" value={form.phone} onChange={set('phone')} autoComplete="tel" />
        </label>
      </div>
      <label>
        Topic
        <select value={form.category} onChange={set('category')}>
          {categories.map((c) => <option key={c}>{c}</option>)}
        </select>
      </label>
      <label>
        Subject
        <input required minLength={3} maxLength={300} value={form.subject} onChange={set('subject')} />
      </label>
      <label>
        Describe the issue
        <textarea required minLength={5} rows={3} value={form.description} onChange={set('description')} />
      </label>
      {error && <p className="hd-error" role="alert">{error}</p>}
      <div className="hd-form-actions">
        <button type="button" className="hd-btn hd-btn-ghost" onClick={onCancel}>Cancel</button>
        <button type="submit" className="hd-btn hd-btn-primary" disabled={sending}>{sending ? 'Creating…' : 'Create ticket'}</button>
      </div>
    </form>
  )
}
