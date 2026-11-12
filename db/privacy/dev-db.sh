#!/usr/bin/env bash
# Local throwaway Postgres for privacy development/tests. NOT a deployment.
# Binds to 127.0.0.1 only and uses trust auth inside a disposable container.
#
#   db/privacy/dev-db.sh up      # start container + apply privacy migration + seed demo communities
#   db/privacy/dev-db.sh down    # remove container
#
# Prints the DSNs:
#   GQ_ADMIN_DSN   migration owner (superuser) - setup/fixtures only
#   GQ_DATABASE_URL  non-owner gq_api login role - what the API uses
set -euo pipefail

NAME="${GQ_DEV_DB_CONTAINER:-gq-privacy-dev}"
PORT="${GQ_DEV_DB_PORT:-54329}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ADMIN_DSN="postgresql://postgres@127.0.0.1:${PORT}/postgres"
API_DSN="postgresql://gq_api_login@127.0.0.1:${PORT}/postgres"

case "${1:-up}" in
  up)
    if ! docker ps --format '{{.Names}}' | grep -qx "$NAME"; then
      docker run -d --name "$NAME" -p "127.0.0.1:${PORT}:5432" \
        -e POSTGRES_HOST_AUTH_METHOD=trust postgres:17-alpine >/dev/null
    fi
    for _ in $(seq 1 40); do
      docker exec "$NAME" pg_isready -U postgres -q && break
      sleep 0.5
    done
    if ! docker exec "$NAME" psql -U postgres -tAc "SELECT 1 FROM pg_namespace WHERE nspname='privacy'" | grep -q 1; then
      docker exec -i "$NAME" psql -U postgres -v ON_ERROR_STOP=1 -q < "$HERE/001_privacy_foundation.sql"
    fi
    docker exec -i "$NAME" psql -U postgres -v ON_ERROR_STOP=1 -q <<'SQL'
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gq_api_login') THEN
    CREATE ROLE gq_api_login LOGIN IN ROLE gq_api;
  END IF;
END $$;
SQL
    docker exec -i "$NAME" psql -U postgres -v ON_ERROR_STOP=1 -q < "$HERE/002_demo_communities.sql"
    echo "GQ_ADMIN_DSN=$ADMIN_DSN"
    echo "GQ_DATABASE_URL=$API_DSN"
    ;;
  down)
    docker rm -f "$NAME" >/dev/null && echo "removed $NAME"
    ;;
  *)
    echo "usage: $0 up|down" >&2; exit 2 ;;
esac
