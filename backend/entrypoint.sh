#!/bin/sh
set -e

echo "==> Applying database migrations"
python manage.py migrate --noinput

echo "==> Collecting static files"
python manage.py collectstatic --noinput

echo "==> Ensuring default admin user exists"
python manage.py create_default_admin

# Daily clean-up: delete client requests rejected more than ~6 months ago
(
  while true; do
    python manage.py purge_rejected_requests || echo "Rejected-request cleanup failed" >&2
    python manage.py purge_public_chat_data || echo "Public-chat retention cleanup failed" >&2
    sleep 86400
  done
) &

echo "==> Starting Gunicorn on :8000"
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --threads 4 \
  --timeout 120 \
  --access-logfile -