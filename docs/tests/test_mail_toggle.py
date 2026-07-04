"""Test: Laufzeit-Schalter für den E-Mail-Versand.

- `booking.mail_config`: Datei-Feld `mail_enabled` (Admin-Toggle) gewinnt,
  sonst der übergebene Default (aus .env `MAIL_ENABLED`).
- `notify._send_email`: sendet nicht, wenn der Schalter aus ist.

Ausführen:  pytest docs/tests/test_mail_toggle.py
"""
import asyncio
import json
from types import SimpleNamespace as NS

import pytest

from booking import mail_config
import notifications.notify as notify


# ─────────────────────────────────────────────── mail_config (Datei-Schalter)

@pytest.fixture
def cfg_file(tmp_path, monkeypatch):
    f = tmp_path / "vereinsconfig.json"
    f.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(mail_config, "_config_file", lambda: f)
    return f


def test_default_wenn_kein_feld(cfg_file):
    # leere Config → Default entscheidet
    assert mail_config.is_enabled(default=True) is True
    assert mail_config.is_enabled(default=False) is False


def test_datei_feld_gewinnt_ueber_default(cfg_file):
    mail_config.set_enabled(False)
    assert mail_config.is_enabled(default=True) is False   # Datei schlägt Default
    mail_config.set_enabled(True)
    assert mail_config.is_enabled(default=False) is True


def test_set_enabled_persistiert(cfg_file):
    mail_config.set_enabled(False)
    data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert data["mail_enabled"] is False


# ─────────────────────────────────────────────── _send_email respektiert Schalter

def _settings():
    return NS(mail_enabled=True, smtp_from="from@x.de", smtp_host="h",
              smtp_port=587, smtp_user="u", smtp_password="p")


def test_send_email_uebersprungen_wenn_aus(monkeypatch):
    calls = {"n": 0}

    async def _fake_send(*a, **k):
        calls["n"] += 1

    monkeypatch.setattr(notify.aiosmtplib, "send", _fake_send)
    monkeypatch.setattr("booking.mail_config.is_enabled", lambda default=True: False)
    asyncio.run(notify._send_email("to@x.de", "Subj", "Body", _settings()))
    assert calls["n"] == 0


def test_send_email_gesendet_wenn_an(monkeypatch):
    calls = {"n": 0}

    async def _fake_send(*a, **k):
        calls["n"] += 1

    monkeypatch.setattr(notify.aiosmtplib, "send", _fake_send)
    monkeypatch.setattr("booking.mail_config.is_enabled", lambda default=True: True)
    asyncio.run(notify._send_email("to@x.de", "Subj", "Body", _settings()))
    assert calls["n"] == 1
