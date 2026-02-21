from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from booking.models import (
    Booking,
    BookingCreate,
    BookingType,
    Series,
    SeriesCreate,
    SeriesRhythm,
    SeriesStatus,
    TokenPayload,
)
from booking.booking import build_booking
from web.config import Settings


def generate_series_dates(
    start_date: date,
    end_date: date,
    rhythm: SeriesRhythm,
    field_is_rasen: bool = False,
) -> list[date]:
    """Erzeugt alle Termindaten einer Serie."""
    interval_days = 7 if rhythm == SeriesRhythm.WOECHENTLICH else 14
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=interval_days)
    return dates


def create_series_with_bookings(
    repo,
    data: SeriesCreate,
    current_user: TokenPayload,
    settings: Settings,
    trainer_name: str,
) -> tuple[Series, list[Booking], list[date]]:
    """
    Legt eine Serie an und erzeugt alle Einzeltermine.

    Gibt zurück:
    - series: die angelegte Serie
    - created: erfolgreich angelegte Buchungen
    - skipped_dates: Termine die übersprungen wurden (Konflikt oder Sperrzeit)
    """
    series = repo.create_series(
        data=data,
        booked_by_id=current_user.sub,
        booked_by_name=current_user.username,
        trainer_name=trainer_name,
    )

    dates = generate_series_dates(
        data.start_date,
        data.end_date,
        data.rhythm,
        field_is_rasen=data.field.is_rasen,
    )

    created: list[Booking] = []
    skipped: list[date] = []

    for d in dates:
        booking_data = BookingCreate(
            field=data.field,
            date=d,
            start_time=data.start_time,
            duration_min=data.duration_min,
            booking_type=BookingType.TRAINING,
        )
        existing = repo.get_bookings_for_date(d)
        blackouts = repo.get_blackouts_for_date(d) if data.field.is_rasen else []

        booking, errors = build_booking(
            repo=repo,
            data=booking_data,
            current_user=current_user,
            settings=settings,
            existing_bookings=existing,
            blackouts=blackouts,
            series_id=series.notion_id,
            mannschaft_override=data.mannschaft.value,
        )
        if errors:
            skipped.append(d)
        else:
            created.append(booking)

    return series, created, skipped


def remove_date_from_series(repo, booking_id: str, current_user: TokenPayload) -> Booking:
    """
    Löst einen Einzeltermin aus der Serie heraus.
    Setzt Serienausnahme=True und Status=Storniert.
    """
    return repo.mark_series_exception(booking_id)


def cancel_series(
    repo,
    series_id: str,
    current_user: TokenPayload,
) -> tuple[Series, list[Booking]]:
    """
    Beendet eine Serie und storniert alle zukünftigen Termine.

    Gibt (series, cancelled_bookings) zurück.
    """
    future_bookings = repo.get_bookings_for_series(series_id, only_future=True)
    cancelled = []
    for booking in future_bookings:
        from booking.models import BookingStatus
        updated = repo.update_booking_status(booking.notion_id, BookingStatus.STORNIERT)
        cancelled.append(updated)

    series = repo.update_series_status(series_id, SeriesStatus.BEENDET)
    return series, cancelled
