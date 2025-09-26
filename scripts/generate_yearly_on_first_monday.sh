#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

YEAR="$(date +%Y)"
DOW="$(date +%u)"   # 1 = maandag
DOM="$(date +%d)"   # dag van de maand met voorloopnul

# Forceer-run wanneer "--force" meegegeven is
if [ "${1:-}" = "--force" ]; then
  docker compose exec -T web python manage.py generate_yearly_invoices --year "$YEAR" --commit
  exit 0
fi

# Normaal pad: alleen eerste maandag van het jaar (dag 01..07 én maandag)
if [ "$DOW" = "1" ] && [ "$DOM" -le 07 ]; then
  docker compose exec -T web python manage.py generate_yearly_invoices --year "$YEAR" --commit
else
  echo "Niet de eerste maandag, niets te doen."
fi
