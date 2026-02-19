from datetime import date, time
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun


def get_sunset(booking_date: date, lat: float, lon: float, name: str) -> time:
    location = LocationInfo(
        name=name,
        region="",
        timezone="Europe/Berlin",
        latitude=lat,
        longitude=lon,
    )
    s = sun(location.observer, date=booking_date, tzinfo=ZoneInfo("Europe/Berlin"))
    return s["sunset"].time().replace(second=0, microsecond=0)


def sunset_warning_text(
    booking_date: date,
    end_time: time,
    lat: float,
    lon: float,
    name: str,
) -> str | None:
    """
    Gibt einen Hinweistext zurück, wenn der Sonnenuntergang vor dem Ende der Buchung liegt.
    Gibt None zurück, wenn kein Hinweis nötig ist.
    """
    sunset = get_sunset(booking_date, lat, lon, name)
    if sunset < end_time:
        return (
            f"Hinweis: Sonnenuntergang um ca. {sunset.strftime('%H:%M')} Uhr – "
            f"der Platz wird vor Ende der Buchung dunkel."
        )
    return None
