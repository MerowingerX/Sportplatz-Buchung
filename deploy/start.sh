#!/usr/bin/env bash
# Bringt die Homepage wieder online.
set -e

echo "==> Starte sportplatz-homepage ..."
systemctl start sportplatz-homepage.service

echo "==> Homepage ist online."
systemctl status sportplatz-homepage.service --no-pager -l
