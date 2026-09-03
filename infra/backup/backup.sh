#!/bin/sh
# pg_dump both staging databases to R2. Rolling retention without any
# list/delete logic: 7 weekday slots overwrite weekly, plus a first-of-month
# slot kept per month. Restore: migrate a fresh DB, then `gunzip -c | psql`.
set -eu
# Without pipefail, `pg_dump | gzip` reports gzip's status, so a pg_dump
# failure is invisible: gzip writes a valid ~20-byte empty archive, `gzip -t`
# passes it, and it overwrites the day's slot with "backup complete" in the
# logs. After a password rotation that is seven consecutive silent overwrites.
# busybox ash supports pipefail.
set -o pipefail

# A dump smaller than this did not contain a database. Measured Aug–Sep 2026:
# ops_engine ~6.8 MB gzipped, litellm ~95 KB; an empty gzip is 20 bytes. The
# floor sits well under the smaller of the two and far above nothing.
MIN_BYTES="${BACKUP_MIN_BYTES:-20000}"

# A cron container that exits non-zero just disappears from Railway, so a
# failure has to leave the machine to be noticed. Both variables unset = the
# failure is only in the logs, which is where it was before this existed.
notify() {
  [ -n "${RESEND_API_KEY:-}" ] && [ -n "${BACKUP_ALERT_EMAIL:-}" ] || return 0
  curl -sS -X POST "https://api.resend.com/emails" \
    -H "Authorization: Bearer $RESEND_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"from\":\"${BACKUP_ALERT_FROM:-Flowgrid <notifications@flowgridos.co.uk>}\",
         \"to\":[\"$BACKUP_ALERT_EMAIL\"],
         \"subject\":\"Flowgrid staging backup FAILED\",
         \"text\":\"$1\"}" \
    >/dev/null || echo "alert delivery failed" >&2
}

on_exit() {
  code=$?
  [ "$code" = 0 ] && return 0
  echo "BACKUP FAILED (exit $code) at $(date -u +%FT%TZ)" >&2
  notify "Flowgrid staging backup exited $code at $(date -u +%FT%TZ). No slot was overwritten. Check the backup service logs."
}
trap on_exit EXIT

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
  # `gzip -t` passes on an empty-but-valid archive, so the size floor is the
  # only check that distinguishes a dump from a well-formed failure.
  size="$(wc -c < "$out" | tr -d ' ')"
  if [ "$size" -lt "$MIN_BYTES" ]; then
    echo "refusing to upload $name: $size bytes, floor is $MIN_BYTES" >&2
    exit 1
  fi
  upload "backups/staging/$name/daily-$(date -u +%a).sql.gz" "$out"
  if [ "$(date -u +%d)" = "01" ]; then
    upload "backups/staging/$name/monthly-$(date -u +%Y-%m).sql.gz" "$out"
  fi
}

dump ops_engine "$OPS_DATABASE_URL"
dump litellm "$LITELLM_DATABASE_URL"
echo "backup complete $(date -u +%FT%TZ)"
