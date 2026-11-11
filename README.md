# Support Agent AI

Three Docker containers, one command:

| Container | What it is | URL |
|---|---|---|
| `support_agent_frontend` | React website (production build, served by Nginx) | http://localhost:3000 |
| `support_agent_admin` | Django admin panel (Gunicorn) | http://localhost:8000/admin/ |
| `support_agent_db` | PostgreSQL (latest image, inside Docker) | internal only |

## Run it

```bash
docker compose up --build
```

First build takes a few minutes. After that, `docker compose up` is enough.

## Admin login

- Username: `admin@soham.com`
- Password: `1234`

The user is created automatically on first start (and skipped if it already exists).
The admin panel is intentionally empty: Django's default Users and Groups are hidden.

## Useful commands

```bash
docker compose up -d          # run in background
docker compose logs -f        # watch logs
docker compose down           # stop everything (data is kept)
docker compose down -v        # stop and DELETE the database volume
```

## Publish a chatbot on your website

After your account is approved, upload and index a document, configure the bot, then open **Dashboard → Publish & API**.
Publishing creates an immutable version of the bot settings, document text, and retrieval vectors. Editing the draft
does not affect the live version. Restoring a historical version replaces the draft; publish it again to make it live.

Create an API key in the dashboard and copy it immediately; the plaintext key is only shown once. Replacing a key
keeps the previous one valid for 24 hours, while revoking keys disables them immediately. Add each exact website
origin to **Allowed websites** before integrating the chat.

The public API flow is:

1. Your server calls `POST /api/public/token/` with `X-API-Key`, the allowlisted `origin`, and the visitor's name/email.
2. Your server returns the 15-minute visitor token to that visitor's browser.
3. The browser sends `POST /api/public/chat/` with the visitor token and reads the SSE answer and source citations.

Never put a production API key in browser code. The dashboard's **API documentation** has copyable examples and
**Try the sample chat** is a test-only playground. The public API allows 1,000 messages per client per month,
10 visitor-token requests per API key per minute, and 10 messages per visitor token per minute. Visitor transcripts
are automatically purged after 90 days by the backend's daily cleanup task.

## Project layout

```
support-agent-ai/
├── docker-compose.yml
├── .env                  # all settings and the default admin credentials
├── backend/              # Django project (config/) + core app
└── frontend/             # React (Vite) site
```

## Before putting this on a real server

- Change `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD` and the admin password in `.env`.
- Set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` to your domain.
- Put HTTPS in front (Nginx/Caddy/Cloudflare).
