#! /bin/bash
# use this to start the application
.venv/bin/uvicorn web.main:app --host 0.0.0.0 --port 1946 --reload

# or this to start the service
#
# file with content:
# /etc/systemd/system/sportplatz-homepage-uvicorn.service
# [Unit]
# Description=Sportplatz Homepage (Uvicorn)
# After=network.target
#
# [Service]
# Type=simple
# User=tus # oder dein Nutzer
# Group=tus
# WorkingDirectory=/home/tus/sportplatz-homepage   # dein Projektordner
# ExecStart=/home/tus/sportplatz-homepage/.venv/bin/uvicorn web.main:app --host 0.0.0.0 --port 1946 --reload
#
# Restart=always
# RestartSec=3
# Environment=PYTHONUNBUFFERED=1
#
# [Install]
# WantedBy=multi-user.target

# and the command to start or restart the service:
# sudo systemctl restart sportplatz-buchung.service
# sudo systemctl start sportplatz-buchung.service