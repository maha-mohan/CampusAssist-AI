// localStorage can be blocked (private mode, strict cookie settings) — never let it break the widget.
const PREFIX = 'college_helpdesk_'

export const storage = {
  get(key) {
    try {
      return window.localStorage.getItem(PREFIX + key)
    } catch {
      return null
    }
  },
  set(key, value) {
    try {
      window.localStorage.setItem(PREFIX + key, value)
    } catch {
      /* ignore */
    }
  },
  remove(key) {
    try {
      window.localStorage.removeItem(PREFIX + key)
    } catch {
      /* ignore */
    }
  },
}

export function visitorId() {
  let id = storage.get('visitor')
  if (!id) {
    id = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()).replace(/-/g, '').slice(0, 32)
    storage.set('visitor', id)
  }
  return id
}

// Answers carry [1]-style citations for staff review; visitors see sources listed below instead.
export const stripCitations = (text) => (text || '').replace(/\s?\[(\d{1,2})\]/g, '')
