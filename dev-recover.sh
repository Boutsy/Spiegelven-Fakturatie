#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
docker-compose stop web || true

check_db() {
  docker-compose run --rm web sh -lc '
set -e
cd /app
python - <<PY
import sqlite3,sys,os
p="db.sqlite3"
if not os.path.exists(p):
    sys.exit(1)
try:
    con=sqlite3.connect(p)
    con.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
    con.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
'
}

if ! check_db; then
  latest="$(ls -t backups/*_db.sqlite3 2>/dev/null | head -n1 || true)"
  if [ -n "$latest" ]; then
    cp -f "$latest" db.sqlite3
    chmod 664 db.sqlite3
  else
    rm -f db.sqlite3 2>/dev/null || true
  fi
fi

docker-compose run --rm web python manage.py migrate
docker-compose up -d web