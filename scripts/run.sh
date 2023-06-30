#!/bin/sh

# If any command in this file, it will fail whole script
set -e

# Wait for db to be up
python manage.py wait_for_db

# Collect all static files and put static directory
python manage.py collectstatic --noinput

# Run migrations before starting app
python manage.py migrate

# Run uwsgi server  port 9000 will be used nginx server to connect to app
uwsgi --socket :9000 --workers 4 --master --enable-threads --module app.wsgi
