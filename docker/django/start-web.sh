#!/bin/sh

# =============================
# Helpers
# =============================
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# =============================
# Django migrations
# =============================
log "Running migrations..."
python manage.py migrate --noinput || {
  log "Migration failed."
  exit 1
}
log "Migrations completed."

#exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers=2 --threads=4