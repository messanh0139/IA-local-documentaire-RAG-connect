#!/bin/sh
set -eu

echo "Waiting for PostgreSQL and initializing database..."

attempt=1
until python -m app.db.init_db; do
  if [ "$attempt" -ge 30 ]; then
    echo "Database initialization failed after $attempt attempts."
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep 2
done

echo "Starting FastAPI..."
exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
