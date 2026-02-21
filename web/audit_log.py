"""
Audit-Logger für Logins und Buchungsaktionen.
Schreibt in logs/audit.log (rotierend, max 5 MB, 3 Backups).
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_DIR  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "audit.log")

os.makedirs(_LOG_DIR, exist_ok=True)

_logger = logging.getLogger("audit")
_logger.setLevel(logging.INFO)
_logger.propagate = False

if not _logger.handlers:
    _handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    _handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    _logger.addHandler(_handler)


def _ip(request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else request.client.host


def log_login_ok(request, username: str) -> None:
    _logger.info("LOGIN     | %-20s | %-20s | OK", _ip(request), username)


def log_login_fail(request, username: str) -> None:
    _logger.info("LOGIN     | %-20s | %-20s | FEHLGESCHLAGEN", _ip(request), username)


def log_logout(request, username: str) -> None:
    _logger.info("LOGOUT    | %-20s | %-20s", _ip(request), username)


def log_booking(request, username: str, booking) -> None:
    _logger.info(
        "BUCHUNG   | %-20s | %-20s | %-16s | %s | %s | %d min | %s",
        _ip(request), username,
        booking.field.value,
        booking.date.strftime("%d.%m.%Y"),
        booking.start_time.strftime("%H:%M"),
        booking.duration_min,
        booking.booking_type.value,
    )


def log_cancel(request, username: str, booking) -> None:
    _logger.info(
        "STORNO    | %-20s | %-20s | %-16s | %s | %s",
        _ip(request), username,
        booking.field.value,
        booking.date.strftime("%d.%m.%Y"),
        booking.start_time.strftime("%H:%M"),
    )
