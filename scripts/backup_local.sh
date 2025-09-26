#!/usr/bin/env bash
set -euo pipefail
# Altijd vanuit de projectroot werken
cd "$(dirname "$0")/.."

mkdir -p .backups

# Volgnummer bijhouden
COUNTER_FILE=".backups/.counter"
if [[ -f "$COUNTER_FILE" ]]; then
  n="$(cat "$COUNTER_FILE")"
else
  n=0
fi
n=$((n+1))
printf '%d' "$n" > "$COUNTER_FILE"
seq="$(printf 'bk-%04d' "$n")"

ts="$(date '+%Y-%m-%d_%H-%M-%S')"
label="${1:-}"
slug="$(printf '%s' "$label" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9._-]+/-/g; s/^-+|-+$//g')"
msg="backup ${seq} ${ts}${slug:+ — ${slug}}"

# Zorg dat we in een Git-repo zitten
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git init
  git checkout -b main || true
fi

# Commit met (desnoods lege) snapshot
git add -A
if ! git commit -m "$msg" >/dev/null 2>&1; then
  git commit --allow-empty -m "$msg" >/dev/null
fi

# Annotated tag
if git rev-parse -q --verify "refs/tags/${seq}" >/dev/null; then
  echo "⚠️ Tag ${seq} bestaat al (vreemd)."
else
  git tag -a "$seq" -m "$msg"
fi

# Zip-archief (zonder .git / .backups / cache)
zip_path=".backups/${seq}_${ts}${slug:+_${slug}}.zip"
zip -qr "$zip_path" . -x ".git/*" ".backups/*" "*/__pycache__/*" "*.pyc" ".DS_Store" || true

echo "✅ Backup gemaakt:"
echo " • Git tag : $seq"
echo " • Zip     : $zip_path"
echo "(Push later: git push origin main --tags  — als je remote is ingesteld)"
