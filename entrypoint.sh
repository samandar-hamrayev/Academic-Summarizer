#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "==> Running database migrations..."
  python manage.py migrate --noinput
fi

echo "==> Starting: $*"
exec "$@"
