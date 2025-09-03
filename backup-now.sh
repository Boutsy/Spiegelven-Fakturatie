#!/usr/bin/env bash
set -e

# ---- Setup ----
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
tar --exclude=.git --exclude=venv --exclude=.venv --exclude=node_modules \
    -czf "backups/repo-$STAMP.tgz" .

echo "== Django dumpdata =="
docker compose exec -T web python manage.py dumpdata \
  --natural-foreign --natural-primary \
  --exclude contenttypes --exclude admin --exclude sessions \
  --exclude auth.permission --exclude authtoken \
  --indent 2 > "backups/django-fixture-$STAMP.json"

echo "== Database dump (Postgres) =="
# Probeer service 'db', anders 'postgres'; sla over als geen van beide bestaat
if CID=$(docker compose ps -q db 2>/dev/null) && [ -n "$CID" ]; then
  if ! docker compose exec -T db bash -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
       > "backups/pgdump-$STAMP.sql"; then
    echo "⚠️  pg_dump via service 'db' mislukte (ga door zonder DB dump)."
  fi
elif CID=$(docker compose ps -q postgres 2>/dev/null) && [ -n "$CID" ]; then
  if ! docker compose exec -T postgres bash -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
       > "backups/pgdump-$STAMP.sql"; then
    echo "⚠️  pg_dump via service 'postgres' mislukte (ga door zonder DB dump)."
  fi
else
  echo "ℹ️  Geen database-service 'db' of 'postgres' gevonden; sla DB dump over."
fi

echo "== Media-archief =="
# Archiveer /app/media indien aanwezig
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
