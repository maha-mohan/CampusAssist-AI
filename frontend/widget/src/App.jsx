import { useEffect, useMemo, useRef, useState } from 'react'
import { createApi } from './api/client'
import { useChat } from './hooks/useChat'
import MessageItem from './components/MessageItem'
import TicketForm from './components/TicketForm'
import { IconChat, IconClose, IconMinus, IconRefresh, IconSend } from './components/Icons'

export default function App({ config }) {
  const api = useMemo(() => createApi(config.api), [config.api])
  const chat = useChat(api)
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [ticketPrefill, setTicketPrefill] = useState(null) // null = form closed
  const listRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (open) {
      chat.init()
      setTimeout(() => inputRef.current?.focus(), 60)
    }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  // Keep the newest message in view.
  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [chat.messages, ticketPrefill])

  // Close with Escape.
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    if (open) window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const submit = (e) => {
    e?.preventDefault()
    if (!text.trim()) return
    chat.send(text)
    setText('')
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const userCount = chat.messages.filter((m) => m.role === 'user').length
  const showChips = chat.ready && userCount === 0 && !ticketPrefill

  const handleChip = (q) => {
    if (/ticket/i.test(q.label)) setTicketPrefill({})
    else chat.send(q.query)
  }

  return (
    <div className={`hd-root hd-pos-${config.position}`}>
      {open && (
        <section className="hd-window" role="dialog" aria-label={`${config.title} chat`}>
          <header className="hd-header">
            <div>
              <p className="hd-title">{config.title}</p>
              <p className="hd-subtitle">Answers from official college documents</p>
            </div>
            <div className="hd-header-actions">
              <button type="button" aria-label="Start a new conversation" title="New conversation" onClick={chat.reset}><IconRefresh /></button>
              <button type="button" aria-label="Minimise chat" title="Minimise" onClick={() => setOpen(false)}><IconMinus /></button>
            </div>
          </header>

          <div className="hd-list" ref={listRef} aria-live="polite">
            {!chat.ready && !chat.error && <p className="hd-muted hd-center">Connecting…</p>}
            {chat.messages.map((m) => (
              <MessageItem key={m.id} msg={m} api={api} onRate={chat.rate} onRaiseTicket={(p) => setTicketPrefill(p || {})} />
            ))}

            {showChips && chat.quickReplies.length > 0 && (
              <div className="hd-chips" aria-label="Common topics">
                {chat.quickReplies.map((q) => (
                  <button key={q.label} type="button" className="hd-chip" onClick={() => handleChip(q)}>{q.label}</button>
                ))}
              </div>
            )}

            {ticketPrefill && (
              <TicketForm
                api={api}
                sessionId={chat.sessionId}
                prefill={ticketPrefill}
                onCancel={() => setTicketPrefill(null)}
                onCreated={(ticket) => {
                  setTicketPrefill(null)
                  chat.pushLocal({ role: 'assistant', kind: 'ticket-success', ticket })
                }}
              />
            )}
          </div>

          {chat.error && (
            <p className="hd-error hd-error-bar" role="alert">
              {chat.error}
              {!chat.ready && <button type="button" onClick={chat.init}>Retry</button>}
            </p>
          )}

          <form className="hd-composer" onSubmit={submit}>
            <label className="hd-sr" htmlFor="hd-input">Type your question</label>
            <textarea
              id="hd-input"
              ref={inputRef}
              rows={1}
              value={text}
              maxLength={config.maxChars}
              placeholder="Ask in English or தமிழ்…"
              onChange={(e) => setText(e.target.value)}
              onKeyDown={onKeyDown}
              disabled={!chat.ready}
            />
            <button type="submit" className="hd-send" aria-label="Send" disabled={!text.trim() || chat.busy || !chat.ready}><IconSend /></button>
          </form>
          <p className="hd-footnote">AI answers can be wrong. Check important dates and fees with the source document.</p>
        </section>
      )}

      <button
        type="button"
        className={`hd-launcher ${open ? 'is-open' : ''}`}
        aria-expanded={open}
        aria-label={open ? 'Close help desk' : 'Open help desk'}
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <IconClose /> : (<><IconChat /><span>Ask the help desk</span></>)}
      </button>
    </div>
  )
}
