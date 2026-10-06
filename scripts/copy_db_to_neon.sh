#!/usr/bin/env bash
# Copy the local Postgres (docker compose "db" service) into an EMPTY Neon database.
#
#   NEON_DATABASE_URL='postgresql://user:pass@ep-xxx.aws.neon.tech/neondb?sslmode=require' \
#     bash scripts/copy_db_to_neon.sh
#
# Uses pg_dump/pg_restore inside the local pgvector container, so no local Postgres tools are needed.
set -euo pipefail

CONTAINER="${DB_CONTAINER:-mrson_rag_db}"
: "${NEON_DATABASE_URL:?Set NEON_DATABASE_URL to the Neon connection string}"
# The app's SQLAlchemy URL may use the "+psycopg2" driver suffix; libpq tools don't accept it.
TARGET="${NEON_DATABASE_URL/postgresql+psycopg2:/postgresql:}"

remote() { docker exec -i "$CONTAINER" psql "$TARGET" -v ON_ERROR_STOP=1 -Atq "$@"; }

existing=$(remote -c "select count(*) from information_schema.tables where table_schema='public'")
if [ "$existing" != "0" ]; then
  echo "Neon database already has $existing tables in 'public'; refusing to overwrite." >&2
  echo "Use a fresh database (or drop its tables) and run again." >&2
  exit 1
fi

echo "Copying local database to Neon..."
docker exec "$CONTAINER" pg_dump -U raguser -d ragdb -Fc --no-owner --no-privileges \
  | docker exec -i "$CONTAINER" pg_restore --no-owner --no-privileges --exit-on-error -d "$TARGET"

echo "Row counts on Neon:"
remote -c "select 'alembic_version', version_num from alembic_version
           union all select 'active chunks', count(*)::text from chunks where is_active
           union all select 'documents', count(*)::text from documents
           union all select 'users', count(*)::text from users
           union all select 'conversations', count(*)::text from conversations"
