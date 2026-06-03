#!/bin/bash
# Automatic ticket sync - runs every 30 minutes
cd /home/devops-machine/Fluidtrust-project/claude-changes
source venv/bin/activate
python manage.py proper_sync --incremental >> /var/log/ticket_sync.log 2>&1
