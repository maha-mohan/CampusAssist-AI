# API reference

Interactive docs: `/api/docs` (Swagger UI) on any running instance. All paths below are under `/api`.

## Public (used by the widget)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Database / Redis / LLM status |
| GET | `/config` | College name, academic year, quick replies |
| POST | `/chat/session` | Start a session → `{session_id, greeting, quick_replies}` |
| POST | `/chat/stream` | **SSE** answer stream. Body `{session_id, message}`. Events: `meta`, `token` (`{text}`), `reset`, `done` (`{message_id, answer, sources, answered, suggest_ticket, ticket_prefill}`), `error` |
| POST | `/chat/message` | Same as stream but returns one JSON response |
| GET | `/chat/session/{id}/messages` | Restore history |
| POST | `/chat/feedback` | `{message_id, session_id, rating: 1 \| -1, comment?}` |
| GET | `/tickets/categories` | Ticket topics |
| POST | `/tickets` | Create ticket `{name, email?, phone?, category, subject, description, session_id?}` (email or phone required) |
| GET | `/tickets/{code}?contact=` | Public status; `contact` must match the ticket's email or phone |
| GET | `/documents/{id}/file` | Source document (active documents only) |

Rate limits: 20 chat messages/minute per IP and per session (configurable), 5 tickets per 10 minutes per IP, 10 logins per 5 minutes per IP.

## Admin (Bearer JWT from `/admin/auth/login`)

| Method | Path | Roles |
|---|---|---|
| POST | `/admin/auth/login` | — |
| GET | `/admin/auth/me` | any |
| POST | `/admin/auth/change-password` | any |
| GET/POST/PATCH | `/admin/users`, `/admin/users/{id}` | super_admin |
| GET | `/admin/departments` | any |
| POST/PUT/DELETE | `/admin/departments[/{id}]` | super_admin |
| GET | `/admin/documents?q=&status=&doc_type=&department_id=&academic_year=&page=` | any |
| POST | `/admin/documents/upload` (multipart: `file, title, doc_type, department_id, academic_year, valid_from, valid_to, replaces_document_id`) | super_admin, dept_admin |
| POST | `/admin/documents/url` | super_admin, dept_admin |
| GET | `/admin/documents/{id}`, `/admin/documents/{id}/chunks` | any |
| PATCH / DELETE | `/admin/documents/{id}` | super_admin, dept_admin |
| POST | `/admin/documents/{id}/reprocess` | super_admin, dept_admin |
| GET | `/admin/faqs?q=` | any |
| POST / PUT / DELETE | `/admin/faqs[/{id}]` | super_admin, dept_admin |
| GET | `/admin/tickets?status=open,in_progress&category=&department_id=&priority=&q=&page=` | any (scoped to own department unless super_admin) |
| GET / PATCH | `/admin/tickets/{id}` (`{status?, priority?, assigned_to?, department_id?, note?, is_public}`) | any (scoped) |
| GET | `/admin/chats?q=&page=`, `/admin/chats/{session_id}` | any |
| GET | `/admin/insights/unanswered?days=`, `/admin/insights/negative-feedback` | any |
| GET | `/admin/analytics/overview?days=` | any |

Errors return `{"detail": "readable message"}`.
