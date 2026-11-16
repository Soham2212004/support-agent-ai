# Support Agent AI

A multi-tenant RAG chatbot platform. Clients sign up, upload a document (or type FAQ entries),
customize a bot's personality, test it, and publish it as either a drop-in embeddable widget or
a REST API for their own frontend. Built with Django, Celery, Postgres + pgvector, Redis, and React.

---

## What's in the box

This started as a simple "upload a PDF, chat with it" tool and grew into a fuller product. Here's
everything currently implemented:

### Core chat & RAG
- Upload a PDF, DOCX, or TXT document — extracted, chunked, and embedded locally (`intfloat/multilingual-e5-small` by default, swappable via env var)
- **FAQ entries** as a second knowledge source — typed question/answer pairs, embedded and searched alongside the document, no file required
- **Document versioning** — replacing a document archives the previous one's metadata (filename, size, chunk count) instead of silently discarding it; a dashboard version history shows past uploads
- A retrieval test box in the dashboard — search your own knowledge base directly and see similarity scores, tagged by source (document vs. FAQ)
- Configurable answer behavior per bot: match strictness (similarity threshold), citation visibility, answer length (short/standard/detailed)
- Tone presets (friendly / professional / concise), custom instructions, fallback message, escalation email, bot avatar, suggested starter questions

### Publishing & integration
- Publishing freezes an immutable snapshot of the bot's settings, document text, and chunk vectors (including FAQ entries) — editing the draft never affects what's live
- Version history with one-click restore (restoring replaces the draft; publish again to go live)
- Secret API key management — shown once, with a 24-hour grace period on rotation and immediate effect on revocation
- Website origin allowlist for CORS-safe public chat
- **Two integration modes, toggled per bot:**
  - **Default widget** — a self-contained `<script>` embed (`widget.js`) with a floating chat bubble, light/dark/auto theming via `data-theme`, starter questions, and human-handoff support. No frontend work required.
  - **Custom integration** — build your own UI against the public REST API (token exchange → streaming chat via SSE)

### Human handoff
- A visitor can request a human mid-conversation (explicit request, or after repeated fallback answers)
- The bot goes silent and the conversation moves to `waiting_human`; the client is emailed and sees it in a dedicated **Handoffs** dashboard tab with an open-count badge
- The client replies directly from the dashboard; the visitor sees the reply within ~5 seconds via polling (no page reload)
- **10-minute reminder email** if nobody's replied yet; **30-minute auto-expiry** hands the conversation back to the bot with a system message; a replied-but-unresolved handoff auto-resolves after 24 hours
- All timers run on a Celery beat schedule, independent of any request being in flight

### Feedback & analytics
- 👍/👎 on every bot answer, in both the dashboard test chat and the public widget
- Downvoted answers get flagged in the Django admin conversation transcript (red tint)
- A dashboard **Analytics** tab: visitor message volume, fallback rate, helpful/unhelpful rating counts, average token usage, "top unanswered questions" (grouped by fallback reason), and "answers visitors rated 👎" (the actual question + actual answer + count — distinct from fallback, since this catches confidently wrong answers)
- Each downvoted Q&A can be annotated with a note and marked "needs attention" / "resolved" directly from the analytics list, so feedback has somewhere to go
- One-click CSV export of a client's own conversation history

### Trust & compliance
- GDPR-style visitor data requests — a visitor can request an export or deletion of their own chat history, verified by an emailed one-time code before anything happens
- A public **Status & changelog** page (`/status`) listing platform updates, managed from Django admin
- An onboarding checklist on first dashboard visit (upload → index → customize → publish), dismissible, driven by real account state rather than a fixed script

### Operational / platform internals
- **Celery + Redis** for all background work — document indexing, FAQ indexing, and the handoff timer loop all run on a worker process, not a bare thread, with automatic retry and backoff on embedding failures
- **Celery beat** runs the once-a-minute handoff timer check
- **Redis-backed rate limiting** for the public API (visitor messages, token requests) — fails open if Redis is briefly unreachable, so a Redis hiccup degrades gracefully instead of taking the chat down
- **Indexing logs** — every document/FAQ indexing attempt (success or failure, with the actual error) is recorded and browsable in Django admin, instead of only existing as a server log line
- **Admin audit logging** — every time staff open a client's document or document-chunk list/detail in Django admin, it's logged (who, what, when, from which IP) — this data is customer-uploaded content, so access is tracked
- **Purge heartbeats** — the daily cleanup commands (expired rejected requests, old visitor transcripts) report a heartbeat; a stale/dead cleanup loop shows a red banner in the Django admin homepage instead of failing silently

---

## Architecture

```
┌─────────────┐      ┌──────────────────┐      ┌─────────────┐
│  frontend   │─────▶│      backend      │─────▶│  postgres   │
│ (React/Vite,│ :3000│  (Django/Gunicorn) │ :8000│  + pgvector │
│  Nginx)     │      │                    │      └─────────────┘
└─────────────┘      └─────────┬──────────┘
                                │
                      ┌─────────┴──────────┐
                      │                    │
               ┌──────▼──────┐     ┌──────▼──────┐
               │    worker    │     │     beat     │
               │  (Celery:    │     │  (Celery     │
               │  indexing)   │     │  scheduler:  │
               └──────┬───────┘     │  handoff     │
                      │             │  timers)     │
               ┌──────▼──────┐     └──────┬───────┘
               │    redis     │◀───────────┘
               │ (broker +    │
               │ rate limits) │
               └──────────────┘
```

| Container | What it is | URL |
|---|---|---|
| `support_agent_frontend` | React site (production build, served by Nginx) | http://localhost:3000 |
| `support_agent_admin` | Django admin + API (Gunicorn) | http://localhost:8000/admin/ |
| `support_agent_worker` | Celery worker — document/FAQ indexing | internal only |
| `support_agent_beat` | Celery beat — handoff reminder/expiry timers | internal only |
| `support_agent_redis` | Redis — Celery broker + rate limiting | internal only |
| `support_agent_db` | PostgreSQL + pgvector | internal only |

---

## Run it

```bash
docker compose up --build
```

First build takes a few minutes (downloads the embedding model). After that, `docker compose up` is enough.

> **Port conflicts:** if `8000` is already taken by another project, the backend is mapped to `8001:8000` in this compose file — check `docker-compose.yml` and adjust to taste.

## Admin login

- Username: `admin@soham.com`
- Password: `1234`

Created automatically on first start (skipped if it already exists). Django's default Users and
Groups are hidden from the admin sidebar to keep it focused on client management.

## Useful commands

```bash
docker compose up -d                        # run in background
docker compose logs -f backend worker beat  # watch the three Python processes
docker compose down                         # stop everything (data is kept)
docker compose down -v                      # stop and DELETE all volumes (db, redis)
docker compose exec backend python manage.py shell   # Django shell
docker compose up -d --build                # rebuild after a code change
```

---

## Publish a chatbot

1. Register, get approved (Django admin → Client requests → Approve).
2. Upload a document and/or add FAQ entries — wait for indexing to finish (status badges show progress).
3. Configure the bot under **Bot Settings**: name, greeting, tone, custom instructions, answer behavior, starter questions, avatar.
4. Test it in **Documents & Test Chat** — try the retrieval search box too, to see what the bot will actually retrieve.
5. Open **Publish & API**:
   - Choose **Default widget** or **Custom integration**.
   - Create an API key — **copy it immediately, it's shown once.** Replacing a key keeps the old one valid for 24 hours; revoking disables it instantly.
   - Add every exact website origin (scheme + host + port, no paths) to **Allowed websites**.
   - Click **Publish**.

### Default widget

Copy the snippet shown in the Publish tab:

```html
<script src="https://your-api-host/widget.js" data-api-key="YOUR_API_KEY" data-theme="auto" async></script>
```

- `data-theme`: `"light"`, `"dark"`, or `"auto"` (follows the visitor's OS preference)
- Done. The floating chat bubble handles everything — visitor identification, streaming replies, starter questions, and "Talk to a human."

### Custom integration

Build your own UI against the public API:

1. Your server calls `POST /api/public/token/` with `X-API-Key`, an allowlisted `origin`, and the visitor's name/email.
2. Return the visitor token to the browser.
3. The browser calls `POST /api/public/chat/` with the token and reads the streamed (SSE) answer and citations.
4. Poll `GET /api/public/chat/poll/?after_seq=N` to pick up human replies if a handoff occurred.

Full request/response examples live in the dashboard's **API documentation** page, generated from
the live code. **Never put a production API key in browser code** — only the visitor token (short-lived, scoped) belongs client-side.

**Limits:** 1,000 messages per client per month, 10 visitor-token requests per API key per minute, 10 messages per visitor token per minute. Visitor transcripts are purged after 90 days.

---

## Project layout

```
support-agent-ai/
├── docker-compose.yml
├── .env                        # all settings and the default admin credentials
├── backend/
│   ├── config/                 # Django project settings, urls, celery app
│   └── core/                   # the one Django app — models, views, tasks
│       ├── models.py           # every table: accounts, documents, FAQ, chunks,
│       │                       #   conversations, handoffs, feedback, analytics support
│       ├── admin.py            # Django admin customization + audit logging
│       ├── chat.py             # dashboard test-chat API (SSE streaming)
│       ├── public_api.py       # public chat API: tokens, streaming, handoff, polling
│       ├── publishing.py       # publish/unpublish/restore, API keys, allowed origins
│       ├── rag.py              # retrieval + prompt assembly + fallback logic
│       ├── indexing.py         # document chunking/embedding (Celery task)
│       ├── faq_indexing.py     # FAQ entry embedding (Celery task)
│       ├── faq.py              # FAQ entry CRUD API
│       ├── documents.py        # upload/search/version-history API
│       ├── handoffs.py         # client-facing handoff reply/resolve API
│       ├── analytics.py        # dashboard analytics + CSV export + downvote notes
│       ├── gdpr.py             # visitor data export/deletion (email-verified)
│       ├── status.py           # public changelog feed
│       ├── widget.py           # the embeddable widget.js
│       ├── tasks.py            # all Celery tasks, including the handoff timer loop
│       └── public_common.py    # rate limiting, origin validation
└── frontend/
    └── src/
        ├── pages/               # Dashboard, Login, Register, PublicChatDemo, StatusPage
        └── components/          # Chat, DocumentUpload, FaqManager, BotSettings,
                                  #   Publishing, Analytics, HandoffRequests,
                                  #   OnboardingChecklist
```

---

## Environment variables

See `.env.example` for the full list with placeholders. Key groups:

| Group | Variables |
|---|---|
| Django | `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` |
| Database | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` |
| Redis / Celery | `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` |
| Embeddings | `EMBEDDING_MODEL` |
| LLM providers | `LLM_PROVIDER`, plus each provider's `*_API_KEY` / `*_MODEL` (Gemini, Grok, OpenAI, Ollama) |
| Email | `DJANGO_EMAIL_BACKEND` (console in dev), `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` |
| Widget | `PUBLIC_API_BASE_URL` — set this explicitly in production so generated widget snippets point at the real public host, not whatever the dashboard happened to load from |
| Rate limits | `CHAT_DAILY_LIMIT` |

---

## Before putting this on a real server

- [ ] Change `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, and the default admin password in `.env`
- [ ] Set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` to your real domain(s)
- [ ] Set `PUBLIC_API_BASE_URL` so embed snippets generate correctly
- [ ] Switch `DJANGO_EMAIL_BACKEND` to real SMTP credentials — GDPR confirmation codes and handoff emails currently only reach container logs (console backend) until this is set
- [ ] Put HTTPS in front (Nginx / Caddy / Cloudflare)
- [ ] Set a real `LLM_PROVIDER` + API key — the demo mode (`Demo (no AI model)`) only quotes the best-matching passage verbatim and is for testing the pipeline wiring, not real answers
- [ ] Confirm `support_agent_beat` is running (`docker compose logs beat`) — without it, handoff reminders and auto-expiry silently never fire
- [ ] Set a real `REDIS_URL` with auth if Redis is exposed beyond the Docker network

---

## A note on scope

This was built incrementally, feature by feature, rather than from a single upfront spec — so some
areas are deliberately simple (one document + FAQ list per client, no multi-tenant plan/billing
tiers yet, no email verification step at signup). The architecture (Celery for background work,
immutable publish snapshots, tenant-scoped queries throughout) is built to extend cleanly if those
become priorities later.