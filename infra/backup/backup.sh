#!/bin/sh
# pg_dump both staging databases to R2. Rolling retention without any
# list/delete logic: 7 weekday slots overwrite weekly, plus a first-of-month
# slot kept per month. Restore: migrate a fresh DB, then `gunzip -c | psql`.
set -eu

upload() {
  key="$1"
  file="$2"
  curl -sSf --aws-sigv4 "aws:amz:auto:s3" \
    --user "$STORAGE_ACCESS_KEY:$STORAGE_SECRET_KEY" \
    -T "$file" \
    -H "Content-Type: application/gzip" \
    "$STORAGE_ENDPOINT/$STORAGE_BUCKET/$key"
  echo "uploaded $key ($(wc -c < "$file") bytes)"
}

dump() {
  name="$1"
  url="$2"
  out="/tmp/$name.sql.gz"
  pg_dump "$url" --no-owner | gzip > "$out"
  gzip -t "$out"
  upload "backups/staging/$name/daily-$(date -u +%a).sql.gz" "$out"
  if [ "$(date -u +%d)" = "01" ]; then
    upload "backups/staging/$name/monthly-$(date -u +%Y-%m).sql.gz" "$out"
  fi
}

dump ops_engine "$OPS_DATABASE_URL"
dump litellm "$LITELLM_DATABASE_URL"
echo "backup complete $(date -u +%FT%TZ)"
