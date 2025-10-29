#!/bin/sh
set -e

echo "==> Running database migrations"
python manage.py migrate --noinput

echo "==> Building Tailwind CSS"
tailwindcss -c tailwind.config.js -i ./assets/input.css -o ./static/css/tailwind.css

echo "==> Collecting static files"
python manage.py collectstatic --noinput

echo "==> Starting Gunicorn"
exec gunicorn app.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
