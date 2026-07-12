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
from booking.booking import build_booking, check_availability, overlaps_are_shareable
from web.config import Settings


def analyze_series_conflicts(
    repo,
    data: SeriesCreate,
) -> dict:
    """Dry-Run vor dem Anlegen: prüft jeden Serientermin auf Konflikte.

    Rückgabe:
    - single: [{date, conflicts}] — teilbare Konflikte mit Einzelbuchungen
    - series: {series_id: {series_id, title, dates: [date], conflicts}} —
      teilbare Konflikte mit Terminen anderer Serien
    - blocked: [{date, conflicts}] — nicht teilbare Konflikte (anderes
      (Teil-)Feld oder DFBnet) → werden immer übersprungen
    """
    single: list[dict] = []
    series_map: dict[str, dict] = {}
    blocked: list[dict] = []

    for d in generate_series_dates(data.start_date, data.end_date, data.rhythm):
        existing = repo.get_bookings_for_date(d)
        conflicts = check_availability(
            existing, data.field, data.start_time, data.duration_min
        )
        if not conflicts:
            continue
        same_field = all(c.field == data.field for c in conflicts)
        if not (same_field and overlaps_are_shareable(data.field, conflicts)):
            blocked.append({"date": d, "conflicts": conflicts})
            continue
        series_conflict = next((c for c in conflicts if c.series_id), None)
        if series_conflict:
            entry = series_map.setdefault(series_conflict.series_id, {
                "series_id": series_conflict.series_id,
                "label": series_conflict.mannschaft or series_conflict.booked_by_name,
                "dates": [],
                "conflicts": [],
            })
            entry["dates"].append(d)
            entry["conflicts"].extend(conflicts)
        else:
            single.append({"date": d, "conflicts": conflicts})

    return {"single": single, "series": series_map, "blocked": blocked}


def generate_series_dates(
    start_date: date,
    end_date: date,
    rhythm: SeriesRhythm,
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
    share_dates: Optional[set[date]] = None,
    share_series_ids: Optional[set[str]] = None,
) -> tuple[Series, list[Booking], list[date]]:
    """
    Legt eine Serie an und erzeugt alle Einzeltermine.

    share_dates: Tage, an denen geteilte Nutzung mit Einzelbuchungen
        explizit bestätigt wurde.
    share_series_ids: Serien, mit denen geteilte Nutzung an allen
        Konflikt-Tagen bestätigt wurde ("immer teilen").

    Gibt zurück:
    - series: die angelegte Serie
    - created: erfolgreich angelegte Buchungen
    - skipped_dates: Termine die übersprungen wurden (Konflikt)
    """
    share_dates = share_dates or set()
    share_series_ids = share_series_ids or set()
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

        allow_share = d in share_dates
        if not allow_share and share_series_ids:
            conflicts = check_availability(
                existing, data.field, data.start_time, data.duration_min
            )
            allow_share = any(c.series_id in share_series_ids for c in conflicts)

        booking, errors = build_booking(
            repo=repo,
            data=booking_data,
            current_user=current_user,
            settings=settings,
            existing_bookings=existing,
            series_id=series.notion_id,
            mannschaft_override=data.mannschaft,
            allow_same_field_overlap=allow_share,
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
