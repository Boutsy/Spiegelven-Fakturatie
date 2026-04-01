#!/bin/sh
set -e

echo "==> Running database migrations"
python manage.py migrate --noinput

echo "==> Building Tailwind CSS"
tailwindcss -c tailwind.config.js -i ./assets/input.css -o ./static/css/tailwind.css

echo "==> Collecting static files"
python manage.py collectstatic --noinput

echo "==> Loading initial data if fixture exists and database is empty"
python manage.py shell -c "
from core.models import Member
import os, subprocess
fixture = 'scripts/initial_data.json'
if os.path.exists(fixture) and Member.objects.count() == 0:
    print('Laden van begindata...')
    subprocess.run(['python', 'manage.py', 'loaddata', fixture], check=True)
    print('Begindata geladen.')
else:
    print('Geen fixture geladen (al data aanwezig of bestand niet gevonden).')
"

echo "==> Creating or updating superuser"
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
import os
u = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
p = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
e = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
if not p:
    print('Geen wachtwoord ingesteld, superuser overgeslagen.')
else:
    obj, created = User.objects.get_or_create(username=u, defaults={'email': e, 'is_staff': True, 'is_superuser': True})
    obj.set_password(p)
    obj.is_staff = True
    obj.is_superuser = True
    obj.save()
    print(f'Superuser {u} {\"aangemaakt\" if created else \"bijgewerkt\"}.')
"

echo "==> Starting Gunicorn"
exec gunicorn app.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
