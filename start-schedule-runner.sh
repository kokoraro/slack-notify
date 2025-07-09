#!/bin/bash
/bin/sleep 5

. "/home/$USER/uptime-robot-bot/venv/bin/activate"
cd "/home/$USER/uptime-robot-bot/app"

set -a
source "/home/$USER/uptime-robot-bot/app/.env"
set +a

python3 scheduler_runner.py