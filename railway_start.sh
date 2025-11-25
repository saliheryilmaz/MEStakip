#!/bin/bash
set -e

echo "🚀 Starting Railway deployment..."

# Debug: Show environment variables
echo "🔍 Environment:"
printenv | sort

# Install dependencies
echo "🔧 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Database migrations
echo "📊 Running migrations..."
python manage.py migrate --noinput

# Create superuser if needed
if [ -f "create_superuser.py" ]; then
    echo "👤 Creating superuser if needed..."
    python create_superuser.py
fi

# Collect static files
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

# Start Gunicorn with debug info
echo "🌐 Starting Gunicorn..."
exec gunicorn metis_admin.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers 1 \
    --timeout 120 \
    --log-level debug \
    --access-logfile - \
    --error-logfile -