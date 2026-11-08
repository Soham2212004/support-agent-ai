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
