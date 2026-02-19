from __future__ import annotations

from datetime import date
from typing import Optional

from booking.models import (
    Booking,
    BookingCreate,
    BookingStatus,
    FieldName,
    TokenPayload,
    UserRole,
)
from utils.time_slots import (
    compute_end_time,
    is_valid_duration,
    is_valid_start_time,
    is_within_booking_hours,
    time_range_overlaps,
)
from utils.sunset import sunset_warning_text
from web.config import Settings


# ------------------------------------------------------------------ Konfliktfelder

_CONFLICT_MAP: dict[FieldName, list[FieldName]] = {
    FieldName.KURA_GANZ: [FieldName.KURA_GANZ, FieldName.KURA_HALB_A, FieldName.KURA_HALB_B],
    FieldName.KURA_HALB_A: [FieldName.KURA_GANZ, FieldName.KURA_HALB_A],
    FieldName.KURA_HALB_B: [FieldName.KURA_GANZ, FieldName.KURA_HALB_B],
    FieldName.RASEN_GANZ: [FieldName.RASEN_GANZ, FieldName.RASEN_HALB_A, FieldName.RASEN_HALB_B],
    FieldName.RASEN_HALB_A: [FieldName.RASEN_GANZ, FieldName.RASEN_HALB_A],
    FieldName.RASEN_HALB_B: [FieldName.RASEN_GANZ, FieldName.RASEN_HALB_B],
    # Turnhalle: Ganz sperrt alles; 2/3 und 1/3 können gleichzeitig laufen
    FieldName.HALLE_GANZ: [FieldName.HALLE_GANZ, FieldName.HALLE_ZWEIDRITTEL, FieldName.HALLE_EINDRITTEL],
    FieldName.HALLE_ZWEIDRITTEL: [FieldName.HALLE_GANZ, FieldName.HALLE_ZWEIDRITTEL],
    FieldName.HALLE_EINDRITTEL: [FieldName.HALLE_GANZ, FieldName.HALLE_EINDRITTEL],
}


def get_conflicting_fields(field: FieldName) -> list[FieldName]:
    """Gibt alle Feldbelegungen zurück, die mit der gewünschten Buchung in Konflikt stehen."""
    return _CONFLICT_MAP[field]


# ------------------------------------------------------------------ Saison

def is_rasen_season(booking_date: date) -> bool:
    """Rasen ist von März bis November buchbar."""
    return 3 <= booking_date.month <= 11


# ------------------------------------------------------------------ Verfügbarkeit

def check_availability(
    existing_bookings: list[Booking],
    field: FieldName,
    start_time,
    duration_min: int,
    exclude_booking_id: Optional[str] = None,
) -> list[Booking]:
    """
    Gibt alle Buchungen zurück, die mit der gewünschten Buchung in Konflikt stehen.
    Eine leere Liste bedeutet: Platz ist frei.

    existing_bookings: alle bestätigten Buchungen für das gewünschte Datum
                       (aus NotionRepository.get_bookings_for_date)
    """
    end_time = compute_end_time(start_time, duration_min)
    conflict_fields = get_conflicting_fields(field)
    conflicts = []

    for booking in existing_bookings:
        if exclude_booking_id and booking.notion_id == exclude_booking_id:
            continue
        if booking.field not in conflict_fields:
            continue
        if time_range_overlaps(start_time, end_time, booking.start_time, booking.end_time):
            conflicts.append(booking)

    return conflicts


def check_blackout(
    blackouts,
    booking_date: date,
    start_time,
    end_time,
):
    """
    Gibt die erste zutreffende Sperrzeit zurück oder None.
    blackouts: Liste von BlackoutPeriod für das jeweilige Datum
    """
    from booking.models import BlackoutType

    for blackout in blackouts:
        if blackout.blackout_type == BlackoutType.GANZTAEGIG:
            return blackout
        if blackout.blackout_type == BlackoutType.ZEITLICH:
            if blackout.start_time and blackout.end_time:
                if time_range_overlaps(start_time, end_time, blackout.start_time, blackout.end_time):
                    return blackout
    return None


# ------------------------------------------------------------------ Buchung erstellen

def validate_booking_input(data: BookingCreate, skip_time_check: bool = False) -> list[str]:
    """Gibt eine Liste von Fehlermeldungen zurück (leer = gültig)."""
    errors = []
    if not is_valid_duration(data.duration_min):
        errors.append(f"Ungültige Buchungsdauer: {data.duration_min} Min. Erlaubt: 60, 90, 180.")
    if not skip_time_check:
        if not is_valid_start_time(data.start_time):
            errors.append(f"Ungültige Startzeit: {data.start_time}. Buchungen nur in 30-Min-Slots ab 16:00.")
        end_time = compute_end_time(data.start_time, data.duration_min)
        if not is_within_booking_hours(data.start_time, end_time):
            errors.append(f"Buchung endet nach 22:00 Uhr ({end_time.strftime('%H:%M')}).")
    return errors


def build_booking(
    repo,
    data: BookingCreate,
    current_user: TokenPayload,
    settings: Settings,
    existing_bookings: list[Booking],
    blackouts=None,
    series_id: Optional[str] = None,
    skip_time_check: bool = False,
    mannschaft_override: Optional[str] = None,
) -> tuple[Booking, list[str]]:
    """
    Erstellt eine Buchung nach vollständiger Validierung.

    Gibt (Booking, []) bei Erfolg zurück,
    oder (None, [Fehlermeldungen]) bei Fehler.

    repo: NotionRepository-Instanz
    """
    errors = validate_booking_input(data, skip_time_check=skip_time_check)
    if errors:
        return None, errors

    end_time = compute_end_time(data.start_time, data.duration_min)

    # Rasen: Saisoncheck
    if data.field.is_rasen and not is_rasen_season(data.date):
        errors.append("Rasen ist nur von März bis November buchbar.")
        return None, errors

    # Rasen: Sperrzeitcheck
    if data.field.is_rasen and blackouts:
        blocked = check_blackout(blackouts, data.date, data.start_time, end_time)
        if blocked:
            reason = blocked.reason or "keine Angabe"
            errors.append(f"Rasen ist gesperrt: {reason}")
            return None, errors

    # Konfliktcheck
    conflicts = check_availability(existing_bookings, data.field, data.start_time, data.duration_min)
    if conflicts:
        names = ", ".join(
            f"{b.field.value} {b.start_time.strftime('%H:%M')}–{b.end_time.strftime('%H:%M')}"
            for b in conflicts
        )
        errors.append(f"Zeitslot nicht verfügbar. Konflikt mit: {names}")
        return None, errors

    # Sonnenuntergangshinweis für Rasen
    sunset_note = None
    if data.field.is_rasen:
        sunset_note = sunset_warning_text(
            data.date, end_time,
            settings.location_lat, settings.location_lon, settings.location_name,
        )

    booking = repo.create_booking(
        data=data,
        booked_by_id=current_user.sub,
        booked_by_name=current_user.username,
        role=current_user.role,
        end_time=end_time,
        sunset_note=sunset_note,
        series_id=series_id,
        mannschaft=mannschaft_override or current_user.mannschaft,
        zweck=data.zweck,
        kontakt=data.kontakt,
    )
    return booking, []


# ------------------------------------------------------------------ DFBnet-Verdrängung

def dfbnet_displace(
    repo,
    data: BookingCreate,
    current_user: TokenPayload,
    settings: Settings,
    existing_bookings: list[Booking],
) -> tuple[Booking, list[Booking]]:
    """
    DFBnet-Buchung mit höchster Priorität:
    1. Alle Konflikt-Buchungen auf Storniert (DFBnet) setzen
    2. Neue Buchung erstellen
    3. (displaced_bookings, new_booking) zurückgeben

    Wirft ValueError wenn current_user keine DFBnet/Administrator-Rolle hat.
    """
    if current_user.role not in (UserRole.DFBNET, UserRole.ADMINISTRATOR):
        raise ValueError("Nur DFBnet oder Administrator darf verdrängen.")

    end_time = compute_end_time(data.start_time, data.duration_min)
    conflicts = check_availability(existing_bookings, data.field, data.start_time, data.duration_min)

    displaced = []
    for conflict in conflicts:
        updated = repo.update_booking_status(conflict.notion_id, BookingStatus.STORNIERT_DFBNET)
        displaced.append(updated)

    # Sunset-Note entfällt bei DFBnet (Kura-Platz), aber der Code bleibt generisch
    sunset_note = None
    if data.field.is_rasen:
        sunset_note = sunset_warning_text(
            data.date, end_time,
            settings.location_lat, settings.location_lon, settings.location_name,
        )

    new_booking = repo.create_booking(
        data=data,
        booked_by_id=current_user.sub,
        booked_by_name=current_user.username,
        role=UserRole.DFBNET,
        end_time=end_time,
        sunset_note=sunset_note,
        zweck=data.zweck,
    )
    return new_booking, displaced
