#!/bin/sh

# Wait for PostgreSQL to be ready
echo "Waiting for database..."
until PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -c '\q'; do
  sleep 2
done

echo "Database is ready. Starting application..."

# Set ownership and permissions
chown -R appuser:appuser /app/logs /app/core/migrations /app/staticfiles
chmod -R 775 /app/logs /app/core/migrations /app/staticfiles
chmod 664 /app/logs/error.log

# Run migrations
echo "Running database migrations..."
python manage.py migrate

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start Gunicorn
exec gunicorn -w 4 -b 0.0.0.0:8000 lsaapp.wsgi:application
