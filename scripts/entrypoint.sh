#!/bin/sh
set -e

echo "==> Running database migrations"
python manage.py migrate --noinput

echo "==> Building Tailwind CSS"
tailwindcss -c tailwind.config.js -i ./assets/input.css -o ./static/css/tailwind.css

echo "==> Collecting static files"
python manage.py collectstatic --noinput

echo "==> Creating superuser if not exists"
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
import os
u = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
p = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
e = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
if p and not User.objects.filter(username=u).exists():
    User.objects.create_superuser(u, e, p)
    print(f'Superuser {u} aangemaakt.')
else:
    print(f'Superuser {u} bestaat al of geen wachtwoord ingesteld.')
"

echo "==> Starting Gunicorn"
exec gunicorn app.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
