#!/bin/bash

# Django Project Startup Script
# FluidTrust Customer Portal

PROJECT_DIR="/home/devops-machine/Fluidtrust-project/claude-changes"
VENV_DIR="$PROJECT_DIR/venv"

echo "🚀 Starting FluidTrust Django Project..."
echo "=================================="

# Change to project directory
cd "$PROJECT_DIR" || exit 1

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Virtual environment not found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    echo "✅ Virtual environment found"
    source venv/bin/activate
fi

# Check if migrations are needed
echo "🔄 Checking database migrations..."
python manage.py migrate

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# Start the server
echo "🌐 Starting Django development server..."
echo "   Server will be available at: http://localhost:8000"
echo "   Press Ctrl+C to stop the server"
echo ""

python manage.py runserver 0.0.0.0:8000
