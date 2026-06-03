#!/bin/bash

# Backup script with cleanup
SOURCE_DIR="/home/devops-machine/Fluidtrust-project/claude-changes"
BACKUP_BASE="/home/devops-machine/backupcode"
TODAY=$(date +%Y-%m-%d)
BACKUP_DIR="$BACKUP_BASE/claudebackup-$TODAY"

echo "Creating backup directory: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

echo "Copying project files (excluding test files and unnecessary items)..."
rsync -av --exclude='test_*.py' \
          --exclude='test_*.html' \
          --exclude='*test*.py' \
          --exclude='*test*.html' \
          --exclude='chart_test.html' \
          --exclude='debug_*.html' \
          --exclude='virtual_charts_demo.html' \
          --exclude='test_forms.html' \
          --exclude='test_reports.html' \
          --exclude='test_simple_reports.html' \
          --exclude='test_buttons.html' \
          --exclude='venv/' \
          --exclude='__pycache__/' \
          --exclude='*.pyc' \
          --exclude='*.log' \
          --exclude='db.sqlite3' \
          --exclude='registration.log' \
          --exclude='server.log' \
          --exclude='pulseway_sync.log' \
          --exclude='.git/' \
          --exclude='*.csv' \
          "$SOURCE_DIR/" "$BACKUP_DIR/"

echo "Setting ownership to devops-machine user..."
chown -R devops-machine:devops-machine "$BACKUP_DIR"

echo "Backup completed successfully!"
echo "Backup location: $BACKUP_DIR"
echo "Backup size:"
du -sh "$BACKUP_DIR"
