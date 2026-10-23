# College AI Help Desk

An AI chatbot for a college website that answers students, parents and visitors **from the college's own documents** (circulars, fee sheets, syllabi, policies), cites its sources, and hands anything it can't answer to the right department as a **help desk ticket**.

- **Frontend:** React.js (JavaScript) — an embeddable chat widget + an admin dashboard
- **Backend:** Python FastAPI, PostgreSQL + pgvector, Redis, arq background worker
- **AI:** OpenAI (chat + embeddings), behind one swappable client. Runs fully offline with a built-in mock provider for development.

---

## What's included

| Area | Features |
|---|---|
| **Chat widget** | One `<script>` tag embed · Shadow DOM (site CSS can't break it) · streaming answers · source links · quick-topic chips · 👍/👎 feedback · ticket form inside the chat · history restored on reload · full-screen on mobile · English, Tamil, Tanglish and Hindi |
| **AI answering (RAG)** | Hybrid search (pgvector + Postgres full-text) with rank fusion · curated FAQ answers first · academic-year aware (prefers the current year, ignores expired docs) · strict "answer only from context, copy numbers exactly" prompt · refuses instead of guessing, then offers a ticket · follow-up question rewriting · answer cache |
| **Tickets** | Created from chat · auto-routed to a department by topic · ticket IDs like `C20261020-001` · status check in chat (needs ticket ID + the email/phone used) · public and internal notes · email alerts to department and student |
| **Knowledge base** | Upload PDF / DOCX / TXT / MD / HTML or add a web page URL · OCR for scanned PDFs (English + Tamil) · tables kept as tables · header/footer cleanup · version replacement ("this circular replaces that one") · valid-from/until dates · chunk preview |
| **Admin dashboard** | Overview led by *questions the bot couldn't answer* · tickets with filters and department scoping · conversations viewer · "Needs attention" (unanswered + not-helpful, with one-click "Answer with an FAQ") · documents · FAQs · users & roles · departments · cost and latency estimates |
| **Security & privacy** | JWT auth with roles (super admin / department admin / staff) · per-IP and per-session rate limits · upload type/size/magic-byte checks · no raw IPs stored · chat retention purge (DPDP-friendly) · audit log · prompt-injection guard in the system prompt |
| **Ops** | Docker Compose (Postgres, Redis, API, worker, Nginx) · Alembic migrations · health endpoint · Sentry hook · backup script · pytest suite · golden-set evaluation script |

---

## Project structure

```
college-ai-helpdesk/
├── backend/                         FastAPI application
│   ├── app/
│   │   ├── main.py                  App entry: CORS, errors, routers
│   │   ├── api/
│   │   │   ├── deps.py              Auth, roles, audit helper
│   │   │   ├── router.py            Route registration
│   │   │   └── routes/
│   │   │       ├── chat.py          POST /chat/session, /chat/stream (SSE), /chat/message, feedback
│   │   │       ├── tickets.py       Public ticket create + status lookup
│   │   │       ├── public.py        /health, /config, document download
│   │   │       └── admin/           auth, users+departments, documents+FAQs, tickets, chats+analytics
│   │   ├── core/                    config, database, security (JWT/bcrypt), redis (rate limit, cache), constants
│   │   ├── models/models.py         SQLAlchemy models (users, documents, chunks, faqs, sessions, messages, tickets…)
│   │   ├── schemas/schemas.py       Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── chat_service.py      Orchestration: intent → FAQ / RAG / ticket flow → streamed answer
│   │   │   ├── retrieval.py         Hybrid vector + keyword search, FAQ matching
│   │   │   ├── llm_client.py        OpenAI client + offline mock
│   │   │   ├── prompts.py           System prompt, fixed multilingual replies
│   │   │   ├── nlu.py               Language + intent detection (no LLM cost)
│   │   │   ├── ingestion.py         Extract → OCR → clean → chunk → embed
│   │   │   ├── ticket_service.py    Ticket codes, routing, notifications
│   │   │   ├── email_service.py     SMTP alerts
│   │   │   └── jobs.py              Queue jobs on the worker (in-process fallback)
│   │   ├── workers/worker.py        arq worker: ingestion, FAQ embeddings, retention purge
│   │   └── scripts/seed.py          Departments, first admin, sample FAQs and documents
│   ├── alembic/                     Database migrations
│   ├── sample_data/                 Demo college documents (clearly marked SAMPLE)
│   ├── tests/                       Unit + end-to-end API tests
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── widget/                      React.js embeddable chat widget (builds to one JS file)
│   │   └── src/ (main.jsx, App.jsx, components/, hooks/useChat.js, api/client.js, styles/widget.css)
│   └── admin/                       React.js admin dashboard (Vite, Tailwind, React Query, Recharts)
│       └── src/ (pages/, components/, api/client.js, store/auth.js)
├── demo/index.html                  Sample college page showing the one-line embed
├── eval/                            golden_set.csv + run_eval.py (answer-accuracy check)
├── infra/                           nginx.conf, Dockerfile.nginx, scripts/backup.sh
├── docs/                            ARCHITECTURE.md, DEPLOYMENT.md, API.md
├── docker-compose.yml               Full stack
└── docker-compose.dev.yml           Just Postgres + Redis for local development
```

---

## Quick start (Docker, about 5 minutes)

```bash
cp backend/.env.example backend/.env
# Edit backend/.env: set SECRET_KEY, FIRST_ADMIN_PASSWORD, and OPENAI_API_KEY (leave empty to try offline)

docker compose up -d --build
docker compose exec api python -m app.scripts.seed --samples
```

Open:
- **Demo college page with the widget:** http://localhost:8080/demo/
- **Admin dashboard:** http://localhost:8080/admin/ (sign in with `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD`)
- **API docs (Swagger):** http://localhost:8080/api/docs

## Local development (without Docker for the apps)

Requirements: Python 3.11+, Node 20+, and Postgres 15+ with pgvector + Redis (easiest: `docker compose -f docker-compose.dev.yml up -d`).

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m app.scripts.seed --samples
uvicorn app.main:app --reload --port 8000              # API at http://localhost:8000/api/docs

# Background worker (separate terminal) — or set INLINE_JOBS=true to process uploads inside the API
arq app.workers.worker.WorkerSettings

# Chat widget (separate terminal) — demo page at http://localhost:5173
cd frontend/widget && npm install && npm run dev

# Admin dashboard (separate terminal) — http://localhost:5174/admin/
cd frontend/admin && npm install && npm run dev
```

> **No OpenAI key yet?** Leave `OPENAI_API_KEY` empty. The mock provider gives extractive answers from the documents so you can build and demo everything. Answer quality jumps once a real key is set.

---

## Embedding the widget on the college website

Add one line before `</body>` on every page (or in the site's footer template):

```html
<script src="https://helpdesk.yourcollege.edu/widget/helpdesk-widget.js"
        data-api="https://helpdesk.yourcollege.edu/api"
        data-title="ABC College Help Desk"
        defer></script>
```

Optional attributes: `data-color="#1f2a5c"` (main colour), `data-accent="#e7a21b"` (launcher colour), `data-position="left"`.
Also add the website's domain to `CORS_ORIGINS` in `backend/.env`.

WordPress: paste the snippet into *Appearance → Theme File Editor → footer.php*, or use a "header & footer scripts" plugin.

---

## Running tests and evaluation

```bash
cd backend
createdb helpdesk_test     # once; needs the pgvector extension available
pytest                     # 17 tests: unit + full API flows (mock LLM, real Postgres)

# Answer accuracy against the golden question set (API must be running)
RATE_LIMIT_PER_MINUTE=1000 uvicorn app.main:app --port 8000 &
python ../eval/run_eval.py --api http://localhost:8000/api
```

Before go-live, grow `eval/golden_set.csv` to **150+ real questions** collected from the admissions office, exam cell and hostel (include Tamil and Tanglish), run it with the real OpenAI key, and aim for **≥ 85%**. Re-run after every major document update.

---

## Going live checklist

1. Replace the sample documents with the real ones (Admin → Documents). Archive or delete the `SAMPLE` docs.
2. Set `CURRENT_ACADEMIC_YEAR`, and tag each document with its academic year and valid-until date.
3. Set a strong `SECRET_KEY` and change the first admin password after the first sign-in.
4. Configure SMTP so departments get new-ticket emails; set each department's alert email.
5. Run the evaluation with the real model; fix gaps with FAQs.
6. Put the API behind HTTPS (see `docs/DEPLOYMENT.md`), enable daily backups.
7. Soft-launch on one page (e.g. Admissions) for a week, review *Needs attention* daily, then add the widget site-wide.

See **docs/ARCHITECTURE.md** for how the answering pipeline works and **docs/DEPLOYMENT.md** for server setup.
