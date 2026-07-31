# Nightly logical-backup cron for staging (Railway's native volume backups
# are plan-gated). Runs backup.sh to completion and exits — Railway's cron
# schedule relaunches it (set on the service: cronSchedule + restart NEVER).
FROM postgres:16-alpine

RUN apk add --no-cache curl

COPY backup.sh /backup.sh
RUN chmod +x /backup.sh

CMD ["/backup.sh"]
