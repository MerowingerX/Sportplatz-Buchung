#!/usr/bin/env bash
# Installiert und aktiviert alle systemd-Services für TuS Cremlingen.
# Muss als root ausgeführt werden.
set -e

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

echo "==> Kopiere Service-Dateien nach $SYSTEMD_DIR ..."
cp "$DEPLOY_DIR/sportplatz-buchung.service"  "$SYSTEMD_DIR/"
cp "$DEPLOY_DIR/sportplatz-homepage.service" "$SYSTEMD_DIR/"
cp "$DEPLOY_DIR/sportplatz-crash@.service"   "$SYSTEMD_DIR/"

echo "==> Lade systemd-Konfiguration neu ..."
systemctl daemon-reload

echo "==> Aktiviere und starte Dienste ..."
systemctl enable --now sportplatz-buchung.service
systemctl enable --now sportplatz-homepage.service

echo ""
echo "Fertig. Status:"
systemctl status sportplatz-buchung.service  --no-pager -l
systemctl status sportplatz-homepage.service --no-pager -l
