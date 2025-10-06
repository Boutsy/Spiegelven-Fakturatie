#!/bin/bash
# Gebruik: ./restore.sh 20250926_094701

if [ -z "$1" ]; then
  echo "Gebruik: $0 <timestamp>"
  exit 1
fi

TS=$1
BASE_DIR="/Users/marcbouts/spiegelven-login"
BACKUP_DIR="$BASE_DIR/backups"

SRC="$BACKUP_DIR/alles-bereikbaar_${TS}_src.tgz"
DB="$BACKUP_DIR/alles-bereikbaar_${TS}_db.sqlite3"

if [ ! -f "$SRC" ]; then
  echo "Broncode-archief niet gevonden: $SRC"
  exit 1
fi

if [ ! -f "$DB" ]; then
  echo "Database-backup niet gevonden: $DB"
  exit 1
fi

echo "Herstellen van backup met timestamp: $TS"

# Eerst de code terugzetten
tar -xzf "$SRC" -C "$BASE_DIR"

# Dan de database terugzetten
cp -f "$DB" "$BASE_DIR/db.sqlite3"

echo "Restore voltooid!"