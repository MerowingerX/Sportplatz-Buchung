"""Test: nach einer Buchung springt das Wochen-Zeitfenster zur Buchungszeit.

Der Kalender rendert ein 6-Stunden-Fenster ab `start_hour` (calendar_week).
Nach dem Anlegen einer Buchung wird der Wochen-View per OOB-Swap neu geladen;
dabei muss `start_hour` so gewählt sein, dass die neue Buchung im Fenster liegt
(vorher fehlte der Parameter → Sprung zurück auf 08:00).

Regel: start_hour = clamp(buchungsstunde - 2, 0, 16)  → ~2h Vorlauf.

Siehe web/routers/bookings.py → calendar_start_hour_for / create_booking.

Ausführen:  pytest docs/tests/test_calendar_start_hour.py
"""
import pytest

from web.routers.bookings import calendar_start_hour_for

WINDOW_HOURS = 6  # calendar_week zeigt start_hour .. start_hour+6


@pytest.mark.parametrize(
    "booking_hour,expected",
    [
        (19, 16),  # Beispiel aus dem Feature-Wunsch → 16:00–22:00
        (10, 8),
        (8, 6),
        (6, 4),
        (21, 16),  # oben geclamped
        (2, 0),    # unten geclamped (hour-2 = 0)
        (1, 0),    # unten geclamped (hour-2 < 0)
        (0, 0),
    ],
)
def test_start_hour_mapping(booking_hour, expected):
    assert calendar_start_hour_for(booking_hour) == expected


@pytest.mark.parametrize("booking_hour", range(0, 22))
def test_buchung_liegt_im_fenster(booking_hour):
    """Die Buchungsstunde muss im gerenderten Fenster [start_hour, start_hour+6) liegen."""
    sh = calendar_start_hour_for(booking_hour)
    assert sh <= booking_hour < sh + WINDOW_HOURS


@pytest.mark.parametrize("booking_hour", range(0, 22))
def test_start_hour_im_erlaubten_bereich(booking_hour):
    """start_hour bleibt im von calendar_week akzeptierten Bereich [0, 16]."""
    sh = calendar_start_hour_for(booking_hour)
    assert 0 <= sh <= 16
