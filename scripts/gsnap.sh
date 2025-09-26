#!/usr/bin/env bash
set -e
git add -A
msg=${1:-"snapshot $(date '+%F %T')"}
git commit -m "$msg" || true
git push
