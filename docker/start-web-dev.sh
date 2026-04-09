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

# =============================
# Start
# =============================
exec python manage.py runserver 0.0.0.0:8000