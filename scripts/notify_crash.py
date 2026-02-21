#!/usr/bin/env python3
"""
Crash-Benachrichtigungsskript für systemd OnFailure.
Wird aufgerufen mit dem Namen des gecrashen Service als Argument.
Liest das Journal, sendet eine E-Mail an ADMIN_EMAIL.
"""
from __future__ import annotations

import os
import smtplib
import subprocess
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import dotenv_values

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(PROJECT_DIR, ".env")


def _get_journal(service_name: str, lines: int = 150) -> str:
    try:
        result = subprocess.run(
            [
                "journalctl",
                "-u", service_name,
                "-n", str(lines),
                "--no-pager",
                "-o", "short-precise",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() or "(keine Logs verfügbar)"
    except Exception as exc:
        return f"Fehler beim Lesen der Logs: {exc}"


def main() -> None:
    service_name = sys.argv[1] if len(sys.argv) > 1 else "unbekannter Dienst"

    cfg = dotenv_values(ENV_FILE)
    smtp_host     = cfg.get("SMTP_HOST", "")
    smtp_port     = int(cfg.get("SMTP_PORT", 587))
    smtp_user     = cfg.get("SMTP_USER", "")
    smtp_password = cfg.get("SMTP_PASSWORD", "")
    smtp_from     = cfg.get("SMTP_FROM", smtp_user)
    admin_email   = cfg.get("ADMIN_EMAIL", smtp_from)

    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    log_text = _get_journal(service_name)

    subject = f"[SURRENDER] {service_name} – {now}"
    body = (
        f"Der Dienst ist 3× innerhalb von 2 Minuten gecrasht.\n"
        f"systemd hat aufgegeben – manueller Eingriff erforderlich!\n\n"
        f"  Dienst:    {service_name}\n"
        f"  Zeitpunkt: {now}\n\n"
        f"Neustart manuell:\n"
        f"  systemctl start {service_name}\n\n"
        f"{'=' * 60}\n"
        f"Journal-Log (letzte 150 Zeilen)\n"
        f"{'=' * 60}\n\n"
        f"{log_text}\n"
    )

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"]    = smtp_from
    msg["To"]      = admin_email
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as s:
            s.starttls()
            s.login(smtp_user, smtp_password)
            s.send_message(msg)
        print(f"Crash-Mail für '{service_name}' gesendet an {admin_email}")
    except Exception as exc:
        print(f"E-Mail-Versand fehlgeschlagen: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
