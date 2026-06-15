#!/usr/bin/env bash
# Бэкап PostgreSQL через pg_dump. Использует DATABASE_URL из окружения.
# Пример (локально/в Railway shell):
#   DATABASE_URL="postgresql://user:pass@host:5432/db" bash scripts/backup_db.sh
set -euo pipefail

URL="${DATABASE_URL:?DATABASE_URL не задан}"
# Убираем SQLAlchemy-суффиксы драйвера, pg_dump их не понимает
PG_URL="${URL/+asyncpg/}"
PG_URL="${PG_URL/+psycopg2/}"
PG_URL="${PG_URL/+psycopg/}"

OUT_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$OUT_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="$OUT_DIR/autorewier_${TS}.sql.gz"

echo "Делаю дамп БД -> $OUT"
pg_dump "$PG_URL" | gzip > "$OUT"
echo "Готово: $OUT ($(du -h "$OUT" | cut -f1))"

# Ротация: оставить последние 14 бэкапов
ls -1t "$OUT_DIR"/autorewier_*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm -f
