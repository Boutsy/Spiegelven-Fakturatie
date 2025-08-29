#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

ts="$(date '+%Y-%m-%d_%H-%M-%S')"
msg="${1:-backup: lokaal herstelpunt $ts}"

mkdir -p backups

# 1) Commit (alleen als er iets te committen is)
git add -A
if git diff --cached --quiet && git diff --quiet; then
  echo "ℹ️  Geen wijzigingen om te committen."
else
  git commit -m "$msg"
fi

# 2) Tag als herstelpunt
tag="backup-$ts"
git tag -a "$tag" -m "$msg" || true

# 3) DB-backup (indien aanwezig)
if [ -f db.sqlite3 ]; then
  cp -p db.sqlite3 "backups/db-$ts.sqlite3"
fi

# 4) Git bundle (volledige repo)
git bundle create "backups/repo-$ts.bundle" --all

# 5) ZIP van de werkmap (zonder .git en zonder vorige backups)
if command -v zip >/dev/null 2>&1; then
  zip -qr "backups/tree-$ts.zip" . -x '.git/*' 'backups/*'
else
  tar -czf "backups/tree-$ts.tgz" --exclude-vcs --exclude='./backups' .
fi

echo "✅ Backup klaar:"
echo " - tag: $tag"
[ -f "backups/repo-$ts.bundle" ] && echo " - bundle: backups/repo-$ts.bundle"
[ -f "backups/tree-$ts.zip" ] && echo " - zip: backups/tree-$ts.zip"
[ -f "backups/tree-$ts.tgz" ] && echo " - tgz: backups/tree-$ts.tgz"
[ -f "backups/db-$ts.sqlite3" ] && echo " - db : backups/db-$ts.sqlite3"
