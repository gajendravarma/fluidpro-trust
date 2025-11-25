#!/bin/bash

# Install requirements
pip install -r requirements.txt

# Make migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser (optional)
echo "Creating superuser..."
python manage.py createsuperuser

# Run server
python manage.py runserver 0.0.0.0:8000
