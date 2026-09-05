#!/bin/sh
set -e

is_true() {
  case "$1" in
    1|true|TRUE|True|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

case "$1" in
  web)
    python manage.py migrate --noinput --fake-initial
    python manage.py dia_sync_zamanlama_kur
    if [ "${CREATE_SUPERUSER:-False}" = "True" ]; then
      python manage.py create_auto_superuser
    fi
    if is_true "${RUN_CELERY_IN_WEB:-False}"; then
      celery -A metis_admin worker -l "${CELERY_LOG_LEVEL:-info}" --hostname="web-worker@%h" &
      WORKER_PID="$!"
      celery -A metis_admin beat -l "${CELERY_LOG_LEVEL:-info}" --scheduler django_celery_beat.schedulers:DatabaseScheduler &
      BEAT_PID="$!"
      gunicorn metis_admin.wsgi:application -c gunicorn.conf.py &
      WEB_PID="$!"

      trap 'kill "$WEB_PID" "$WORKER_PID" "$BEAT_PID" 2>/dev/null || true' INT TERM
      wait "$WEB_PID"
    else
      exec gunicorn metis_admin.wsgi:application -c gunicorn.conf.py
    fi
    ;;
  worker)
    exec celery -A metis_admin worker -l "${CELERY_LOG_LEVEL:-info}"
    ;;
  beat)
    exec celery -A metis_admin beat -l "${CELERY_LOG_LEVEL:-info}" --scheduler django_celery_beat.schedulers:DatabaseScheduler
    ;;
  *)
    exec "$@"
    ;;
esac
