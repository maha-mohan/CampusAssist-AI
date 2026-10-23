# Free deployment (no server purchase)

| Part | Free service | Notes |
|---|---|---|
| Database (Postgres + pgvector) | [Neon](https://neon.tech) | Free tier, pgvector supported, does not expire |
| API (FastAPI) | [Render](https://render.com) free web service | Sleeps after ~15 min idle; first request then takes ~30–60 s |
| Chat widget + admin dashboard + demo page | Netlify, Cloudflare Pages or Vercel | Static files, always on |
| AI | Gemini API | Free tier has rate and daily limits |
| Redis | not needed | The app falls back to an in-memory cache and rate limiter |

Limits to know: the free API sleeps when idle, uploaded files are lost whenever Render restarts the
container (the database keeps everything that was indexed), and the Gemini free tier can throttle a busy site.
For a portfolio demo or a small pilot this is fine.

## 1. Database (Neon)
1. Create a project at neon.tech and copy the connection string.
2. Change its start to `postgresql+asyncpg://` and its query to `?ssl=require`, so it looks like
   `postgresql+asyncpg://USER:PASSWORD@ep-xxxx.region.aws.neon.tech/neondb?ssl=require`.
   (Remove `channel_binding=require` if present.) The pgvector extension is created by the first migration.

## 2. API (Render)
1. Push this repo to GitHub. `.env` is git-ignored; never commit your API key.
2. In Render: **New → Blueprint**, pick the repo. It reads `render.yaml`.
3. Fill the prompted secrets: `DATABASE_URL` (from step 1), `OPENAI_API_KEY` (your Gemini key),
   `FIRST_ADMIN_PASSWORD`, and `CORS_ORIGINS` (set after step 3, e.g. `["https://your-site.netlify.app"]`).
4. Deploy. Check `https://YOUR-API.onrender.com/api/health` shows `"database":"ok"`.

## 3. Load the college documents
Free Render instances have no shell, so run the seed from your own computer against the Neon database:

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://...?ssl=require" PYTHONIOENCODING=utf-8 \
  .venv/Scripts/python -m app.scripts.seed --samples      # Windows (Git Bash)
```
It needs `OPENAI_BASE_URL`, `EMBEDDING_MODEL=gemini-embedding-001`, `EMBEDDING_DIM=1536` and the key in
`backend/.env` (already set locally). Later, upload real documents from the admin dashboard.

## 4. Frontends (one static site)
```bash
bash infra/scripts/build_static_site.sh https://YOUR-API.onrender.com/api
```
Upload the generated `site/` folder:
- **Netlify:** drag the folder onto app.netlify.com/drop.
- **Cloudflare Pages:** Create project → Direct Upload → select the folder.

Then put the final site address into `CORS_ORIGINS` on Render and redeploy.

You get:
- Demo page with the chat widget: `https://YOUR-SITE/demo/`
- Admin dashboard: `https://YOUR-SITE/admin/` (sign in with `FIRST_ADMIN_EMAIL` and your password)

## 5. Embed on a college website
```html
<script src="https://YOUR-SITE/widget/helpdesk-widget.js"
        data-api="https://YOUR-API.onrender.com/api" data-title="ABC College Help Desk" defer></script>
```
Add that website's address to `CORS_ORIGINS` as well.

## Keep the API awake (optional)
A free uptime monitor (e.g. UptimeRobot) that pings `https://YOUR-API.onrender.com/api/health` every
10 minutes avoids the cold start during working hours. Render's free monthly hours allow roughly one
always-on service.
