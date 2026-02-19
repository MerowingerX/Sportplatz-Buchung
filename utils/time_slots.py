from datetime import datetime, time, timedelta

BOOKING_START = time(16, 0)
BOOKING_END = time(22, 0)
SLOT_MINUTES = 30
VALID_DURATIONS = [60, 90, 180]


def get_all_start_slots() -> list[time]:
    """Gibt alle gültigen Startzeiten zurück: 16:00 bis 21:30."""
    slots = []
    current = datetime.combine(datetime.today(), BOOKING_START)
    end = datetime.combine(datetime.today(), time(21, 30))
    while current <= end:
        slots.append(current.time())
        current += timedelta(minutes=SLOT_MINUTES)
    return slots


def compute_end_time(start: time, duration_min: int) -> time:
    dt = datetime.combine(datetime.today(), start) + timedelta(minutes=duration_min)
    return dt.time()


def time_range_overlaps(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    """Prüft ob zwei halboffene Zeitintervalle [a_start, a_end) und [b_start, b_end) überlappen."""
    return a_start < b_end and b_start < a_end


def is_valid_start_time(t: time) -> bool:
    return t in get_all_start_slots()


def is_valid_duration(duration_min: int) -> bool:
    return duration_min in VALID_DURATIONS


def is_within_booking_hours(start: time, end: time) -> bool:
    return start >= BOOKING_START and end <= BOOKING_END
