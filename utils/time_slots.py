from datetime import datetime, time, timedelta

BOOKING_START = time(8, 0)
BOOKING_END = time(22, 0)
SLOT_MINUTES = 15
MIN_DURATION_MINUTES = 15
MAX_DURATION_MINUTES = 840  # 14 h (8:00–22:00)

# Legacy-Konstante (Notion-Import-Snapping etc.). Für die Dauer-Validierung
# nicht mehr maßgeblich — diese läuft jetzt über MIN/MAX_DURATION_MINUTES.
VALID_DURATIONS = [60, 90, 180]


def get_all_start_slots() -> list[time]:
    """Gibt alle gültigen Startzeiten zurück: 08:00 bis 21:45."""
    slots = []
    current = datetime.combine(datetime.today(), BOOKING_START)
    # Letzte Startzeit = BOOKING_END minus ein Slot (21:45 bei 15-Min-Raster).
    last_start = (datetime.combine(datetime.today(), BOOKING_END)
                  - timedelta(minutes=SLOT_MINUTES))
    while current <= last_start:
        slots.append(current.time())
        current += timedelta(minutes=SLOT_MINUTES)
    return slots


def get_duration_options() -> list[int]:
    """Auswählbare Buchungsdauern in Minuten.

    15-Min-Schritte bis 4 h, danach Stundenschritte bis 14 h. Deckt den
    Alltag (Training/Spiel/Turnier) feingranular ab, hält das Dropdown aber
    handhabbar.
    """
    fine = list(range(MIN_DURATION_MINUTES, 240 + 1, SLOT_MINUTES))
    coarse = list(range(300, MAX_DURATION_MINUTES + 1, 60))
    return fine + coarse


def compute_end_time(start: time, duration_min: int) -> time:
    dt = datetime.combine(datetime.today(), start) + timedelta(minutes=duration_min)
    return dt.time()


def time_range_overlaps(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    """Prüft ob zwei halboffene Zeitintervalle [a_start, a_end) und [b_start, b_end) überlappen."""
    return a_start < b_end and b_start < a_end


def is_valid_start_time(t: time) -> bool:
    return t in get_all_start_slots()


def is_valid_duration(duration_min: int) -> bool:
    return (
        duration_min % SLOT_MINUTES == 0
        and MIN_DURATION_MINUTES <= duration_min <= MAX_DURATION_MINUTES
    )


def is_within_booking_hours(start: time, end: time) -> bool:
    return start >= BOOKING_START and end <= BOOKING_END
