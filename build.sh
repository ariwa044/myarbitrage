#!/bin/bash

# Exit on error
set -e

# Run migrations (ensure database schema is up-to-date)
echo "Running migrations..."
python manage.py migrate --noinput

# Collect static files for WhiteNoise
echo "Collecting static files..."
python manage.py collectstatic --noinput
