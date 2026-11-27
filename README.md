# Support Agent AI

A multi-tenant RAG chatbot platform. Clients sign up, verify their email, get approved, upload a
document (or type FAQ entries), customize a bot's personality, test it, and publish it as either a
drop-in embeddable widget or a REST API for their own frontend. Built with Django, Celery, Postgres
+ pgvector, Redis, and React — with two interchangeable RAG pipelines (a plain-Python baseline and
a LangGraph-based enhanced pipeline) backed by a real measured evaluation harness, and a 64-test
suite covering tenant isolation, the handoff state machine, both pipelines, plan limits, token
revocation, soft-delete, and login rate limiting.

---

## What's in the box

### Account lifecycle
- Sign-up → **email verification** (signed link, 24h expiry) → **pending** → staff approval in Django admin
- Disposable-email domain blocking at sign-up
- **Password reset** by emailed one-time link (1h expiry)
- **Change password** and **log out everywhere**, both backed by real token revocation — a `token_version` counter on each account means every token issued before a password change or an explicit logout is rejected immediately, not just until it naturally expires
- **Suspended** status: read-only dashboard access and data export stay available; publishing, editing, and the public API stop working immediately
- Full account **export** (ZIP of JSON/CSV: account, bot settings, document, FAQ entries, conversations, leads) and **self-serve deletion**, both gated behind password confirmation
- **Login rate limiting** — per-IP and per-account attempt caps (Redis-backed), returning 429 before credentials are even checked once the limit is hit

### Core chat & RAG
- Upload a PDF, DOCX, or TXT document — extracted, chunked, and embedded locally (`intfloat/multilingual-e5-small` by default, swappable via env var)
- **FAQ entries** as a second knowledge source — typed question/answer pairs, embedded and searched alongside the document, no file required
- **Document versioning** — replacing a document archives the previous one's metadata instead of discarding it; a dashboard version history shows past uploads
- **Soft-delete with a 30-day restore window** for both documents and FAQ entries — deleting something doesn't destroy it immediately, and a "recently deleted" panel lets you undo it
- A retrieval test box in the dashboard — search your own knowledge base directly and see similarity scores, tagged by source (document vs. FAQ)
- Configurable answer behavior per bot: match strictness (similarity threshold), citation visibility, answer length (short/standard/detailed)
- Tone presets (friendly / professional / concise), custom instructions, fallback message, escalation email, bot avatar, suggested starter questions
- **Two interchangeable RAG pipelines, selectable per bot:**
  - **Baseline** — plain-Python retrieval + a single-shot prompt, fast and simple
  - **Enhanced** — a LangGraph graph doing intent classification, wide retrieval + cross-encoder reranking, evidence grading with query rewriting (up to 2 retries), and a prompt-injection guard that short-circuits straight to the fallback message before retrieval ever runs
- An **evaluation harness** (`manage.py run_evaluation`) that scores either pipeline against a JSON question dataset — retrieval hit rate, correct-decline rate, latency percentiles, token counts — and can produce a baseline-vs-enhanced comparison table. Runs for free against the local "fake" demo provider or any real configured LLM.

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

### Conversations, feedback & analytics
- A **Conversations** dashboard tab — every real visitor conversation, searchable by name/email, paginated, with a full transcript view (citations, feedback, human/system messages included)
- 👍/👎 on every bot answer, in both the dashboard test chat and the public widget
- Downvoted answers get flagged in the Django admin conversation transcript (red tint)
- A dashboard **Analytics** tab: visitor message volume, fallback rate, helpful/unhelpful rating counts, average token usage, "top unanswered questions" (grouped by fallback reason, with one-click **convert to a FAQ entry**), and "answers visitors rated 👎" (the actual question + actual answer + count — distinct from fallback, since this catches confidently wrong answers)
- Each downvoted Q&A can be annotated with a note and marked "needs attention" / "resolved" directly from the analytics list
- A **Leads** dashboard tab (paginated) tracking every unique visitor identity per client, with first/last-seen timestamps and CSV export
- A **daily lead digest email** summarizing new and returning leads from the last 24 hours
- One-click CSV export of a client's own conversation history

### Plans & billing (no payment processing)
- A `Plan` model (Free / Pro / Internal) driving per-client message limits, daily test-chat caps, and document/FAQ counts — not hardcoded globals
- Clients can submit an **upgrade request** from their dashboard; staff action it from Django admin, which applies the plan change
- **Usage warning emails** at 80% and 100% of a client's monthly message limit, sent at most once per threshold per month
- A **global daily LLM budget switch** — tracks estimated spend across all test-chat usage and automatically pauses test chat (not live published bots) once a configurable daily cap is hit

### Trust & compliance
- GDPR-style visitor data requests — a visitor can request an export or deletion of their own chat history, verified by an emailed one-time code before anything happens
- A public **Status & changelog** page (`/status`) listing platform updates, managed from Django admin
- Public **Pricing**, **Terms**, **Privacy**, and **Contact** pages (Contact is rate-limited and saves to Django admin)
- An onboarding checklist on first dashboard visit (upload → index → customize → publish), dismissible, driven by real account state rather than a fixed script

### Operational / platform internals
- **Celery + Redis** for all background work — document indexing, FAQ indexing, usage-warning checks, the lead digest, and the handoff timer loop all run on worker/beat processes, not a bare thread, with automatic retry and backoff on embedding failures
- **Celery beat** runs the handoff timer check every minute, usage warnings hourly, and the lead digest daily
- **Redis-backed rate limiting** for the public API (visitor messages, token requests) and for login — fails open if Redis is briefly unreachable for public chat, so a Redis hiccup degrades gracefully instead of taking the chat down
- A `/api/health/` endpoint reporting database and pgvector status
- **Indexing logs** — every document/FAQ indexing attempt (success or failure, with the actual error) is recorded and browsable in Django admin
- **Admin audit logging** — every time staff open a client's document or document-chunk list/detail in Django admin, it's logged (who, what, when, from which IP)
- **Purge heartbeats** — the daily cleanup commands report a heartbeat; a stale/dead cleanup loop shows a red banner in the Django admin homepage instead of failing silently

### Automated tests
64 tests (`backend/core/tests*.py`) covering:
- **Tenant isolation** — a second client can never read, modify, or delete another client's documents, FAQ entries, leads, bot settings, conversations, or handoffs (every check returns 404, not a leaked 403)
- **The handoff state machine** — creation, reply, resolve, the 10-minute reminder, 30-minute auto-expiry, and 24-hour auto-resolve, plus confirming the bot genuinely stays silent while a handoff is open
- **Both RAG pipelines** — fallback triggers on weak evidence, the enhanced pipeline's injection guard blocks an attack before retrieval runs, small talk and human-request intents route correctly
- **Plan limits and usage counters**, including a real concurrency test (10 threads hammering the same account's monthly counter) proving the atomic `UPDATE ... WHERE count < limit` pattern never overcounts
- **Token revocation** — password change, password reset, and "log out everywhere" all genuinely invalidate previously issued tokens
- **Soft-delete** — a deleted document/FAQ entry disappears from search and publish, and restore genuinely brings it back within the 30-day window
- **Login rate limiting** — the attempt past the limit is blocked with 429 before credentials are checked, and separate IPs/accounts don't share buckets

Run them with `docker compose exec backend python manage.py test core -v 2`.

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
               │  indexing,   │     │  scheduler:  │
               │  FAQ         │     │  handoff     │
               │  embedding)  │     │  timers,     │
               └──────┬───────┘     │  usage       │
                      │             │  warnings,   │
               ┌──────▼──────┐     │  lead digest)│
               │    redis     │◀────┴──────┬───────┘
               │ (broker +    │
               │ rate limits) │
               └──────────────┘
```

| Container | What it is | URL |
|---|---|---|
| `support_agent_frontend` | React site (production build, served by Nginx) | http://localhost:3000 |
| `support_agent_admin` | Django admin + API (Gunicorn) | http://localhost:8000/admin/ |
| `support_agent_worker` | Celery worker — document/FAQ indexing | internal only |
| `support_agent_beat` | Celery beat — handoff timers, usage warnings, lead digest | internal only |
| `support_agent_redis` | Redis — Celery broker + rate limiting | internal only |
| `support_agent_db` | PostgreSQL + pgvector | internal only |

---

## Run it

```bash
docker compose up --build
```

First build takes a few minutes (downloads the embedding and reranker models). After that,
`docker compose up` is enough.

> **Port conflicts:** if `8000` is already taken by another project, the backend is mapped to
> `8001:8000` in this compose file — check `docker-compose.yml` and adjust to taste.

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
docker compose exec backend python manage.py shell       # Django shell
docker compose exec backend python manage.py test core -v 2   # run the full test suite
docker compose up -d --build                # rebuild after a code change
```

---

## Sign up and get approved

1. Register at `/register`.
2. Check `docker compose logs backend` for the verification email (console backend by default — see
   [Setting up real email](#setting-up-real-email-gmail-smtp) to send real ones).
3. Click the verification link (or paste the token at `/verify-email`) — status moves to **pending**.
4. Approve the account from Django admin → Client management → Client requests.

## Publish a chatbot

1. Upload a document and/or add FAQ entries under **Documents & Test Chat** — wait for indexing to finish (status badges show progress).
2. Configure the bot under **Bot Settings**: name, greeting, tone, custom instructions, answer behavior, pipeline (baseline/enhanced), starter questions, avatar.
3. Test it in **Documents & Test Chat** — try the retrieval search box too, to see what the bot will actually retrieve.
4. Open **Publish & API**:
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
5. Call `POST /api/public/handoff/` to let the visitor request a human.

Full request/response examples live in the dashboard's **API documentation** page. **Never put a
production API key in browser code** — only the visitor token (short-lived, scoped) belongs
client-side.

**Default limits (per-plan now, not hardcoded):** Free plan starts at 200 messages/month and 50
test messages/day — see Django admin → Plans to adjust. Rate limits: 10 visitor-token requests per
API key per minute, 10 messages per visitor token per minute. Visitor transcripts are purged after
90 days.

---

## Running an evaluation

```bash
docker compose exec backend python manage.py run_evaluation \
  --account-email you@example.com \
  --dataset evaluation/datasets/sample.json \
  --pipeline baseline

docker compose exec backend python manage.py run_evaluation \
  --account-email you@example.com \
  --dataset evaluation/datasets/sample.json \
  --pipeline enhanced \
  --compare-with evaluation/results/baseline-<timestamp>.json
```

Uses the free local "fake" provider by default (`--provider fake`); pass `--provider ollama` (or
any other configured provider) for a real-LLM run. Results and a comparison table are saved under
`evaluation/results/`. Edit `evaluation/datasets/sample.json`'s `expected_source` fields to match
your actual uploaded content for a meaningful `retrieval_hit_rate`.

---

## Project layout

```
support-agent-ai/
├── docker-compose.yml
├── .env                        # all settings and the default admin credentials
├── evaluation/
│   ├── datasets/                # evaluation question sets (JSON)
│   └── results/                 # saved evaluation runs + comparison tables
├── backend/
│   ├── config/                  # Django project settings, urls, celery app
│   └── core/                    # the one Django app — models, views, tasks, tests
│       ├── models.py            # every table: accounts, plans, documents, FAQ, chunks,
│       │                        #   conversations, handoffs, leads, feedback, usage
│       ├── admin.py             # Django admin customization + audit logging
│       ├── api.py               # auth: register, login, verify, reset, change password, logout-everywhere
│       ├── chat.py               # dashboard test-chat API (SSE streaming)
│       ├── public_api.py        # public chat API: tokens, streaming, handoff, polling
│       ├── publishing.py        # publish/unpublish/restore, API keys, allowed origins
│       ├── rag.py               # baseline retrieval + prompt assembly + fallback logic
│       ├── rag_enhanced.py      # LangGraph pipeline: intent, reranker, rewrite, injection guard
│       ├── reranker.py          # local cross-encoder reranking
│       ├── injection_guard.py   # prompt-injection detection (heuristic or HF classifier)
│       ├── evaluation.py        # scoring metrics used by run_evaluation
│       ├── indexing.py          # document chunking/embedding (Celery task)
│       ├── faq_indexing.py      # FAQ entry embedding (Celery task)
│       ├── faq.py               # FAQ entry CRUD + soft-delete/restore API
│       ├── documents.py         # upload/search/version-history/soft-delete API
│       ├── handoffs.py          # client-facing handoff reply/resolve API
│       ├── conversations.py     # client-facing conversation list/transcript API
│       ├── leads.py             # leads list + CSV export
│       ├── analytics.py         # dashboard analytics + CSV export + downvote notes
│       ├── upgrades.py          # plan upgrade requests
│       ├── public_pages.py      # public config (pricing data) + contact form
│       ├── gdpr.py              # visitor data export/deletion (email-verified)
│       ├── account_export.py    # full client account export (ZIP) + self-serve deletion
│       ├── status.py            # public changelog feed
│       ├── widget.py            # the embeddable widget.js
│       ├── health.py            # /api/health/
│       ├── tasks.py             # all Celery tasks: indexing, handoff timers, usage warnings, lead digest
│       ├── llm_budget.py        # global daily LLM spend tracking + pause switch
│       ├── public_common.py     # rate limiting, origin validation, plan-aware usage limits
│       └── tests*.py            # the 64-test suite, split by concern
└── frontend/
    └── src/
        ├── pages/                # Dashboard, Login, Register, VerifyEmail, ForgotPassword,
        │                         #   ResetPassword, Pricing, Terms, Privacy, Contact,
        │                         #   StatusPage, PublicChatDemo
        └── components/           # Chat, DocumentUpload, FaqManager, BotSettings, Publishing,
                                   #   Analytics, Conversations, Leads, HandoffRequests,
                                   #   AccountSettings, OnboardingChecklist
```

---

## Environment variables

See `.env.example` for the full list with placeholders. Key groups:

| Group | Variables |
|---|---|
| Django | `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` |
| Database | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` |
| Redis / Celery | `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` |
| Embeddings / reranking | `EMBEDDING_MODEL`, `RERANK_MODEL` |
| Enhanced pipeline | `INJECTION_MODEL` (optional — leave unset to use the free local heuristic), `RAG_RETRIEVE_WIDE_K`, `RAG_RERANK_KEEP`, `RAG_RERANK_MIN_SIMILARITY`, `RAG_MAX_QUERY_REWRITES` |
| LLM providers | `LLM_PROVIDER`, plus each provider's `*_API_KEY` / `*_MODEL` (Gemini, Grok, OpenAI, Ollama) |
| LLM budget | `LLM_PRICE_IN`, `LLM_PRICE_OUT`, `LLM_DAILY_BUDGET` |
| Email | `DJANGO_EMAIL_BACKEND` (console in dev), `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` |
| Frontend links in emails | `FRONTEND_BASE_URL` (used to build verification/reset links) |
| Widget | `PUBLIC_API_BASE_URL` — set this explicitly in production so generated widget snippets point at the real public host |
| Limits | `CHAT_DAILY_LIMIT` (fallback only — per-plan limits in Django admin take precedence) |

---

## Setting up real email (Gmail SMTP)

By default, every email (verification, password reset, handoff notifications, usage warnings, the
lead digest) just prints to `docker compose logs backend` via Django's console email backend — free,
zero setup, fine for local development. To send real emails for free via your own Gmail account:

```env
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your.email@gmail.com
EMAIL_HOST_PASSWORD=your-16-char-app-password
DEFAULT_FROM_EMAIL=your.email@gmail.com
```

Generate the app password under your Google Account → Security → 2-Step Verification → App
passwords (requires 2FA enabled). Free tier allows roughly 500 emails/day, far more than needed
here. No code changes required — just set these and rebuild.

---

## Before putting this on a real server

- [ ] Change `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, and the default admin password in `.env`
- [ ] Set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` to your real domain(s)
- [ ] Set `PUBLIC_API_BASE_URL` and `FRONTEND_BASE_URL` so generated links/snippets are correct
- [ ] Set up real SMTP credentials (see above) — otherwise every email only reaches container logs
- [ ] Put HTTPS in front (Nginx / Caddy / Cloudflare)
- [ ] Set a real `LLM_PROVIDER` + API key — the demo mode (`Demo (no AI model)`) only quotes the best-matching passage verbatim, for testing pipeline wiring, not real answers
- [ ] Confirm `support_agent_beat` is running (`docker compose logs beat`) — without it, handoff reminders/auto-expiry, usage warnings, and the lead digest silently never fire
- [ ] Set a real `REDIS_URL` with auth if Redis is exposed beyond the Docker network
- [ ] Review the Free/Pro/Internal plan limits in Django admin and adjust for your actual pricing
- [ ] Replace the login rate limiter's per-minute approximation with a dedicated 15-minute-TTL lock if stricter brute-force protection is needed (currently reuses the general-purpose per-minute bucket — documented simplification, not a bug)

---

## A note on scope

This evolved feature-by-feature through an extended build-and-debug process rather than from a
single upfront spec. A few things are worth knowing if you're reading the code:

- **One document + a FAQ list per client**, not a full multi-document knowledge base. FAQ entries
  cover most of the "more than one thing to upload" need, but there's no per-document versioning
  beyond the single active document + its archive.
- **The enhanced pipeline's `classify_intent` and `rewrite_query` nodes fall back to local
  heuristics** when running against the free "fake" demo provider, since that provider can't
  meaningfully follow a classification instruction — this is intentional, not a bug, and is called
  out in `rag_enhanced.py`'s module docstring.
- **Login rate limiting reuses a per-minute Redis bucket** rather than a dedicated 15-minute lock,
  so the "15 minutes" framing in the UI is an approximation of "resets at the next minute boundary,
  repeatedly, until genuinely spaced out." Documented above as a known simplification.
- The architecture (Celery for all background work, immutable publish snapshots, tenant-scoped
  queries enforced at the view layer and verified by tests, soft-delete with a real restore path)
  is built to extend cleanly — adding true multi-document support or a stricter login lockout are
  both additive changes, not rewrites.