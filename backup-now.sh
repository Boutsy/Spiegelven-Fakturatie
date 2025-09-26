#!/usr/bin/env bash
set -e

STAMP=$(date +"%Y-%m-%d-%H%M")
mkdir -p backups

echo "== Git checkpoint =="
if git rev-parse --verify "backup-$STAMP" >/dev/null 2>&1; then
  echo "Branch backup-$STAMP bestaat al; blijf op je huidige branch."
else
  git checkout -b "backup-$STAMP"
fi
git add -A
git commit -m "backup $STAMP" || true
git tag -a "backup-$STAMP" -m "pre-next-session backup" || true

echo "== Repo tarball =="
# Sluit 'backups/' uit zodat het tar-bestand niet zichzelf meeneemt.
tar --exclude=.git --exclude=venv --exclude=.venv --exclude=node_modules \
    --exclude=backups \
    -czf "backups/repo-$STAMP.tgz" .

echo "== Django dumpdata =="
# Bouw de exclude-lijst dynamisch (alleen authtoken als geïnstalleerd)
EXCLUDES=(--natural-foreign --natural-primary
          --exclude contenttypes --exclude admin --exclude sessions
          --exclude auth.permission)

if docker compose exec -T web python manage.py shell -c \
  "from django.conf import settings; import sys; sys.stdout.write('1' if 'rest_framework.authtoken' in settings.INSTALLED_APPS else '0')" \
  | grep -q 1; then
  EXCLUDES+=(--exclude authtoken)
fi

docker compose exec -T web python manage.py dumpdata \
  "${EXCLUDES[@]}" --indent 2 > "backups/django-fixture-$STAMP.json"

echo "== Database dump (Postgres) =="
if CID=$(docker compose ps -q db 2>/dev/null) && [ -n "$CID" ]; then
  docker compose exec -T db bash -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
    > "backups/pgdump-$STAMP.sql" || echo "⚠️  pg_dump via service 'db' mislukte (overslaan)."
elif CID=$(docker compose ps -q postgres 2>/dev/null) && [ -n "$CID" ]; then
  docker compose exec -T postgres bash -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
    > "backups/pgdump-$STAMP.sql" || echo "⚠️  pg_dump via service 'postgres' mislukte (overslaan)."
else
  echo "ℹ️  Geen database-service 'db' of 'postgres' gevonden; sla DB dump over."
fi

echo "== Media-archief =="
if docker compose exec -T web sh -lc 'cd /app && [ -d media ]'; then
  docker compose exec -T web sh -lc 'cd /app && tar -czf - media' \
    > "backups/media-$STAMP.tgz"
else
  echo "ℹ️  /app/media niet gevonden; sla media-archief over."
fi

echo "== Samenvatting =="
ls -lh backups
git status -sb
git tag --list | tail -n 5
