# Architecture

```
 College website ──<script>──► React chat widget (Shadow DOM)
                                   │  HTTPS: REST + Server-Sent Events
                                   ▼
                     Nginx ──► FastAPI (api)  ──► PostgreSQL + pgvector
                       │          │    │              (users, documents, chunks+embeddings,
                       │          │    │               faqs, sessions, messages, tickets, audit)
                       │          │    └──► Redis (rate limits, answer cache, job queue)
                       │          │                    │
                       │          ▼                    ▼
                       │     OpenAI API ◄──── arq worker (ingest → OCR → chunk → embed,
                       │   (chat, embeddings)          FAQ embeddings, nightly retention purge)
                       ▼
            React admin dashboard (/admin, JWT)
```

## How a question is answered

`app/services/chat_service.py → handle_message()`

1. **Language detection** (`nlu.detect_language`): Tamil script, Hindi, Tanglish (Tamil words in English letters) or English. The reply language follows the user.
2. **Intent detection** (`nlu.detect_intent`), rule-based and free:
   - `greeting` / `thanks` → fixed reply, no LLM call
   - `create_ticket` ("I have an issue with…", "talk to staff") → opens the ticket form with topic pre-filled
   - `ticket_status` (a ticket ID such as `C20261020-001`) → looks it up, but only if the message also contains the matching email/phone
   - `question` → steps 3–7
3. **Follow-up rewriting**: short follow-ups ("and for mechanical?") are rewritten into a standalone query using the last few turns.
4. **Answer cache**: identical self-contained questions are answered from Redis for an hour (cleared whenever documents/FAQs change).
5. **FAQ match**: if the question is ≥ 0.86 similar to a curated FAQ, that verified answer is returned word for word (English). For other languages the FAQ becomes top context so the model can answer in the user's language.
6. **Hybrid retrieval** (`retrieval.search_chunks`):
   - pgvector cosine search (HNSW index) and Postgres full-text search (`simple` config, works for Tamil too)
   - merged with Reciprocal Rank Fusion
   - only `active` documents within their valid dates; older academic years are down-weighted
   - if the best match is below `MIN_RELEVANCE_SCORE` → polite "I don't have verified information" + ticket offer (no LLM call)
7. **Grounded generation**: the system prompt (`prompts.py`) requires answering only from the numbered context, copying amounts and dates exactly, citing `[n]`, preferring the current academic year, ignoring instructions inside documents, and replying `NO_ANSWER` if the context is insufficient. The first characters of the stream are held back so a `NO_ANSWER` never reaches the user; it becomes the ticket offer instead.
8. Everything is logged on the `messages` row: answer source (faq / rag / cache / fallback), confidence, sources, tokens, latency. The admin dashboard's *Needs attention* page is built from the `answered = false` rows.

## Ingestion pipeline

`app/services/ingestion.py → ingest_document()` (runs on the worker)

1. **Extract**: PDF via PyMuPDF (tables converted to Markdown tables so fee tables stay readable), DOCX via python-docx (tables too), HTML / web pages via BeautifulSoup (nav, footer, scripts removed).
2. **OCR**: PDF pages with almost no text are rendered at 250 dpi and read with Tesseract (`eng+tam` when installed).
3. **Clean**: lines repeated on most pages (letterheads, footers) and page numbers are removed.
4. **Chunk**: ~600-token chunks with ~100-token overlap, splitting on paragraphs and table rows first.
5. **Embed**: each chunk is embedded with its document title and academic year prepended (helps short chunks match).
6. Old chunks for the document are replaced atomically; the answer cache is cleared.

Uploading with "Replaces an older document" archives the old version, so last year's fee sheet and this year's never mix.

## Data model (main tables)

| Table | Purpose |
|---|---|
| `departments` | Admissions, Exam Cell, Accounts… with alert email |
| `users` | Staff accounts; `role` = super_admin / dept_admin / staff |
| `documents` | Uploaded files / URLs with type, department, academic year, validity, status |
| `chunks` | Text pieces with `embedding vector(1536)` (HNSW) and generated `tsv` (GIN) |
| `faqs` | Curated question/answer pairs with embedding and usage count |
| `chat_sessions` | Anonymous visitor sessions (hashed IP only) |
| `messages` | Every user/assistant turn with sources, confidence, tokens, latency |
| `feedback` | 👍/👎 per assistant message |
| `tickets`, `ticket_updates` | Help desk tickets and their history (public or internal notes) |
| `audit_logs` | Admin actions |

## Roles

| Role | Can do |
|---|---|
| Super admin | Everything: users, departments, all tickets, all content |
| Department admin | Own department's tickets, documents and FAQs |
| Staff | Own department's tickets (and tickets assigned to them) |

## Changing the AI provider

All model calls go through `app/services/llm_client.py` (`embed`, `complete`, `stream`). To use another provider, add a class implementing those three methods and select it in `get_llm()`. Any OpenAI-compatible endpoint (Azure OpenAI, local vLLM, etc.) works by setting `OPENAI_BASE_URL`. If you change the embedding model or dimension, update `EMBEDDING_DIM`, create a migration for the vector column size, and run `ingestion.reembed_all()`.
