import { create } from 'zustand'

const KEY = 'helpdesk_admin_auth'

function load() {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) || 'null')
  } catch {
    return null
  }
}

// Token kept in sessionStorage: it's cleared when the browser tab closes (safer on shared office PCs).
export const useAuth = create((set) => ({
  token: load()?.token || null,
  user: load()?.user || null,
  login: (token, user) => {
    try {
      sessionStorage.setItem(KEY, JSON.stringify({ token, user }))
    } catch { /* ignore */ }
    set({ token, user })
  },
  setUser: (user) =>
    set((s) => {
      try {
        sessionStorage.setItem(KEY, JSON.stringify({ token: s.token, user }))
      } catch { /* ignore */ }
      return { user }
    }),
  logout: () => {
    try {
      sessionStorage.removeItem(KEY)
    } catch { /* ignore */ }
    set({ token: null, user: null })
  },
}))

export const can = (user, action) => {
  const role = user?.role
  const rules = {
    manageUsers: ['super_admin'],
    manageDepartments: ['super_admin'],
    manageContent: ['super_admin', 'dept_admin'],
    moveTickets: ['super_admin', 'dept_admin'],
  }
  return (rules[action] || []).includes(role)
}
