#!/bin/bash
set -e

echo "Waiting for Postgres at ${POSTGRES_HOST}:${POSTGRES_PORT:-5432}..."
until nc -z "$POSTGRES_HOST" "${POSTGRES_PORT:-5432}"; do
  sleep 0.5
done
echo "Postgres is ready."

if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "Applying migrations..."
  python manage.py migrate --noinput
else
  echo "Skipping migrations (RUN_MIGRATIONS != true)."
fi

# In production nginx serves /static/ from a volume shared with this container,
# so the files have to be collected into it first.
if [ "$COLLECT_STATIC" = "true" ]; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput --clear
fi

exec "$@"
