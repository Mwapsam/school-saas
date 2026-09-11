#!/bin/sh
set -e

echo "Starting Pinewood Portal..."

if [ "$DJANGO_ENV" = "production" ]; then

    echo "Collecting static files..."
    python manage.py collectstatic --noinput

    echo "Starting Gunicorn..."

    exec gunicorn pinewood.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers ${GUNICORN_WORKERS:-3} \
        --worker-class gthread \
        --threads ${GUNICORN_THREADS:-4} \
        --max-requests 1000 \
        --max-requests-jitter 100 \
        --timeout 60 \
        --graceful-timeout 30 \
        --keep-alive 10 \
        --preload \
        --log-level warning \
        --access-logfile - \
        --error-logfile -

else

    echo "Running development migrations..."
    python manage.py makemigrations --noinput
    python manage.py migrate --noinput

    echo "Starting development server..."
    exec python manage.py runserver 0.0.0.0:8000

fi