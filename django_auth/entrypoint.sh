#!/bin/sh

# Wait for MySQL to be ready
echo "Waiting for MySQL..."
while ! nc -z mysql 3306; do
  sleep 1
done
echo "MySQL is up!"

# Drop tables that may have been created by FastAPI with wrong schema
echo "Clearing conflicting tables..."
mysql -h mysql -u root -pValidator@2024 -D content_validator -e "DROP TABLE IF EXISTS reports; DROP TABLE IF EXISTS validation_matches; DROP TABLE IF EXISTS validations; DROP TABLE IF EXISTS template_files; DROP TABLE IF EXISTS templates; DROP TABLE IF EXISTS users;"

# Run migrations
echo "Running migrations..."
python manage.py makemigrations authentication
python manage.py migrate

# Seed users (creates admin/admin etc)
echo "Seeding users..."
python manage.py seed_users

# Start server
echo "Starting server..."
exec python manage.py runserver 0.0.0.0:8001