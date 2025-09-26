#!/usr/bin/env bash
set -e
docker compose exec -T web python manage.py check -v 0
