#!/usr/bin/env bash
# Nimmt die Homepage vom Netz (Buchungssystem läuft weiter).
set -e

echo "==> Stoppe sportplatz-homepage ..."
systemctl stop sportplatz-homepage.service

echo "==> Homepage ist offline."
echo "    Wieder starten: bash deploy/start.sh"
