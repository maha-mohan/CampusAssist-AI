import axios from 'axios'
import { useAuth } from '../store/auth'

// In production the admin is served from the same domain as the API (nginx).
// For a separate API host set VITE_API_URL, e.g. https://helpdesk.college.edu/api
export const API_URL = import.meta.env.VITE_API_URL || '/api'

export const http = axios.create({ baseURL: API_URL, timeout: 60000 })

http.interceptors.request.use((config) => {
  const token = useAuth.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401 && !error.config.url.includes('/auth/login')) {
      useAuth.getState().logout()
    }
    error.message = error.response?.data?.detail || error.message
    return Promise.reject(error)
  },
)

const get = (url, params) => http.get(url, { params }).then((r) => r.data)
const post = (url, body) => http.post(url, body).then((r) => r.data)
const patch = (url, body) => http.patch(url, body).then((r) => r.data)
const put = (url, body) => http.put(url, body).then((r) => r.data)
const del = (url) => http.delete(url).then((r) => r.data)

export const api = {
  login: (email, password) => post('/admin/auth/login', { email, password }),
  me: () => get('/admin/auth/me'),
  changePassword: (body) => post('/admin/auth/change-password', body),

  overview: (days = 14) => get('/admin/analytics/overview', { days }),
  unanswered: (params) => get('/admin/insights/unanswered', params),
  negativeFeedback: (params) => get('/admin/insights/negative-feedback', params),

  tickets: (params) => get('/admin/tickets', params),
  ticket: (id) => get(`/admin/tickets/${id}`),
  updateTicket: (id, body) => patch(`/admin/tickets/${id}`, body),
  ticketCategories: () => get('/tickets/categories'),

  documents: (params) => get('/admin/documents', params),
  document: (id) => get(`/admin/documents/${id}`),
  documentChunks: (id) => get(`/admin/documents/${id}/chunks`),
  uploadDocument: (formData, onUploadProgress) =>
    http.post('/admin/documents/upload', formData, { onUploadProgress }).then((r) => r.data),
  addUrl: (body) => post('/admin/documents/url', body),
  updateDocument: (id, body) => patch(`/admin/documents/${id}`, body),
  reprocessDocument: (id) => post(`/admin/documents/${id}/reprocess`),
  deleteDocument: (id) => del(`/admin/documents/${id}`),
  docTypes: () => get('/admin/meta/doc-types'),

  faqs: (params) => get('/admin/faqs', params),
  createFaq: (body) => post('/admin/faqs', body),
  updateFaq: (id, body) => put(`/admin/faqs/${id}`, body),
  deleteFaq: (id) => del(`/admin/faqs/${id}`),

  chats: (params) => get('/admin/chats', params),
  chat: (id) => get(`/admin/chats/${id}`),

  users: () => get('/admin/users'),
  createUser: (body) => post('/admin/users', body),
  updateUser: (id, body) => patch(`/admin/users/${id}`, body),

  departments: () => get('/admin/departments'),
  createDepartment: (body) => post('/admin/departments', body),
  updateDepartment: (id, body) => put(`/admin/departments/${id}`, body),
  deleteDepartment: (id) => del(`/admin/departments/${id}`),

  documentFileUrl: (id) => `${API_URL}/documents/${id}/file`,
}
