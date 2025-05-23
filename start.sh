#!/bin/bash
/bin/sleep 5

. "/home/$USER/uptime-robot-bot/venv/bin/activate"
cd "/home/$USER/uptime-robot-bot/app"

set -a
source "/home/$USER/uptime-robot-bot/app/.env"
set +a

exec gunicorn -w 1 -b 127.0.0.1:$PORT --access-logfile "/home/$USER/uptime-robot-bot/logs/access.log" --error-logfile "/home/$USER/uptime-robot-bot/logs/error.log" app:app