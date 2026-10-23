// Small fetch-based API client for the widget (no axios: keeps the embed script light,
// and streaming needs fetch anyway).

export function createApi(baseUrl) {
  // Resolve relative values like "/api" against the page so URL building always works.
  const base = new URL(baseUrl.replace(/\/$/, ''), window.location.href).toString().replace(/\/$/, '')

  async function request(path, { method = 'GET', body, params } = {}) {
    const url = new URL(base + path, window.location.href)
    if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
    const res = await fetch(url, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      const err = new Error(data.detail || `Request failed (${res.status})`)
      err.status = res.status
      throw err
    }
    return data
  }

  /**
   * Streams a chat answer over Server-Sent Events.
   * onEvent receives {type: 'meta'|'token'|'reset'|'done'|'error', ...}
   */
  async function streamMessage(sessionId, message, onEvent, signal) {
    const res = await fetch(base + '/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message }),
      signal,
    })
    if (!res.ok || !res.body) {
      const data = await res.json().catch(() => ({}))
      const err = new Error(data.detail || `Request failed (${res.status})`)
      err.status = res.status
      throw err
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
      let idx
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        const dataLines = raw.split('\n').filter((l) => l.startsWith('data:')).map((l) => l.slice(5).trimStart())
        if (!dataLines.length) continue // ping / comment
        try {
          onEvent(JSON.parse(dataLines.join('\n')))
        } catch {
          /* ignore malformed event */
        }
      }
    }
  }

  return {
    config: () => request('/config'),
    createSession: (payload) => request('/chat/session', { method: 'POST', body: payload }),
    history: (sid) => request(`/chat/session/${sid}/messages`),
    feedback: (payload) => request('/chat/feedback', { method: 'POST', body: payload }),
    categories: () => request('/tickets/categories'),
    createTicket: (payload) => request('/tickets', { method: 'POST', body: payload }),
    streamMessage,
    absolute: (path) => (path && path.startsWith('/') ? new URL(path, base).toString() : path),
  }
}
