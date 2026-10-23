import { useCallback, useEffect, useRef, useState } from 'react'
import { storage, visitorId } from '../lib/storage'

let localId = 0
const nextId = () => `local-${++localId}`

/** All chat state: session lifecycle, history restore, streaming send, feedback. */
export function useChat(api) {
  const [sessionId, setSessionId] = useState(() => storage.get('session'))
  const [messages, setMessages] = useState([])
  const [quickReplies, setQuickReplies] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [ready, setReady] = useState(false)
  const abortRef = useRef(null)

  const start = useCallback(async () => {
    const s = await api.createSession({ visitor_id: visitorId(), page_url: window.location.href.slice(0, 1000) })
    storage.set('session', s.session_id)
    setSessionId(s.session_id)
    setQuickReplies(s.quick_replies || [])
    setMessages([{ id: nextId(), role: 'assistant', content: s.greeting, greeting: true }])
    return s.session_id
  }, [api])

  // Restore a previous conversation (same browser) or start fresh.
  const init = useCallback(async () => {
    if (ready) return
    setError(null)
    try {
      const cfg = await api.config().catch(() => null)
      if (cfg?.quick_replies) setQuickReplies(cfg.quick_replies)
      const saved = storage.get('session')
      if (saved) {
        try {
          const hist = await api.history(saved)
          if (hist.length) {
            setMessages(hist.map((m) => ({ ...m, done: true })))
            setReady(true)
            return
          }
        } catch {
          storage.remove('session')
        }
      }
      await start()
      setReady(true)
    } catch {
      setError("The help desk can't be reached right now. Check your connection and try again.")
    }
  }, [api, ready, start])

  const patchLast = (fn) =>
    setMessages((prev) => {
      const copy = prev.slice()
      copy[copy.length - 1] = fn(copy[copy.length - 1])
      return copy
    })

  const send = useCallback(
    async (text) => {
      const message = text.trim()
      if (!message || busy) return
      setError(null)
      setBusy(true)
      let sid = sessionId
      try {
        if (!sid) sid = await start()
      } catch {
        setBusy(false)
        setError("The help desk can't be reached right now. Try again in a moment.")
        return
      }
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: 'user', content: message },
        { id: nextId(), role: 'assistant', content: '', pending: true },
      ])
      const controller = new AbortController()
      abortRef.current = controller
      const attempt = async (activeSid) =>
        api.streamMessage(
          activeSid,
          message,
          (ev) => {
            if (ev.type === 'token') patchLast((m) => ({ ...m, pending: false, content: m.content + ev.text }))
            else if (ev.type === 'reset') patchLast((m) => ({ ...m, content: '' }))
            else if (ev.type === 'done')
              patchLast((m) => ({
                ...m,
                id: ev.message_id,
                content: ev.answer,
                sources: ev.sources,
                answered: ev.answered,
                suggestTicket: ev.suggest_ticket,
                ticketPrefill: ev.ticket_prefill,
                pending: false,
                done: true,
              }))
            else if (ev.type === 'error') throw Object.assign(new Error(ev.message), { status: 404 })
          },
          controller.signal,
        )
      try {
        await attempt(sid)
      } catch (err) {
        if (err.name === 'AbortError') return
        if (err.status === 404) {
          // Session expired (e.g. purged) → start a new one and retry once.
          try {
            storage.remove('session')
            const s = await api.createSession({ visitor_id: visitorId(), page_url: window.location.href.slice(0, 1000) })
            storage.set('session', s.session_id)
            setSessionId(s.session_id)
            await attempt(s.session_id)
            return
          } catch {
            /* fall through */
          }
        }
        patchLast((m) => ({ ...m, pending: false, failed: true, content: '' }))
        setError(
          err.status === 429
            ? "You're sending messages quickly. Wait a few seconds, then send again."
            : "That message didn't go through. Check your connection and send it again.",
        )
      } finally {
        setBusy(false)
        abortRef.current = null
      }
    },
    [api, busy, sessionId, start],
  )

  const rate = useCallback(
    async (messageId, rating) => {
      setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, rating } : m)))
      try {
        await api.feedback({ message_id: messageId, session_id: sessionId, rating })
      } catch {
        /* feedback is best-effort */
      }
    },
    [api, sessionId],
  )

  const pushLocal = useCallback((msg) => setMessages((prev) => [...prev, { id: nextId(), ...msg }]), [])

  const reset = useCallback(async () => {
    abortRef.current?.abort()
    storage.remove('session')
    setMessages([])
    setReady(false)
    await start()
    setReady(true)
  }, [start])

  useEffect(() => () => abortRef.current?.abort(), [])

  return { sessionId, messages, quickReplies, busy, error, ready, init, send, rate, pushLocal, reset, setError }
}
