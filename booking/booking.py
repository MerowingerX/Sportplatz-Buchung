from __future__ import annotations

from datetime import date
from typing import Optional

import booking.field_config as _fc
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

def get_conflicting_fields(field: FieldName, all_fields: Optional[list[FieldName]] = None) -> list[FieldName]:
    """
    Gibt alle Felder zurück, die mit dem gegebenen Feld in Konflikt stehen.
    Konfliktlogik: Präfix-Prüfung — A blockiert AA/AB und umgekehrt.
    """
    if all_fields is None:
        all_fields = list(FieldName)
    return [
        f for f in all_fields
        if f.value.startswith(field.value) or field.value.startswith(f.value)
    ]


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


# ------------------------------------------------------------------ Buchung erstellen

def validate_booking_input(data: BookingCreate, skip_time_check: bool = False) -> list[str]:
    """Gibt eine Liste von Fehlermeldungen zurück (leer = gültig)."""
    errors = []
    if not is_valid_duration(data.duration_min):
        errors.append(f"Ungültige Buchungsdauer: {data.duration_min} Min. Erlaubt: 15–840 Min in 15-Min-Schritten.")
    if not skip_time_check:
        if not is_valid_start_time(data.start_time):
            errors.append(f"Ungültige Startzeit: {data.start_time}. Buchungen nur in 15-Min-Slots ab 8:00.")
        end_time = compute_end_time(data.start_time, data.duration_min)
        if not is_within_booking_hours(data.start_time, end_time):
            errors.append(f"Buchung endet nach 22:00 Uhr ({end_time.strftime('%H:%M')}).")
    return errors


def user_teams(repo, current_user: TokenPayload) -> set[str]:
    """Namen aller Teams, denen der User zugewiesen ist (primär oder sekundär via
    M:N) plus sein Token-Team `current_user.mannschaft`."""
    teams = {m.name for m in repo.get_mannschaften_for_user(current_user.sub)}
    if current_user.mannschaft:
        teams.add(current_user.mannschaft)
    return teams


def user_may_book_for(repo, current_user: TokenPayload, mannschaft_name: Optional[str]) -> bool:
    """True, wenn der User für die Mannschaft buchen darf.
    - Ohne Team (`None`): immer erlaubt.
    - Administrator/DFBnet: alle Teams.
    - Sonst: nur Teams, denen der User zugewiesen ist.
    """
    if not mannschaft_name:
        return True
    if current_user.role in (UserRole.ADMINISTRATOR, UserRole.DFBNET):
        return True
    return mannschaft_name in user_teams(repo, current_user)


def build_booking(
    repo,
    data: BookingCreate,
    current_user: TokenPayload,
    settings: Settings,
    existing_bookings: list[Booking],
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

    # Buchungsrecht: Nicht-Admins/-DFBnet dürfen nur für Teams buchen, denen sie
    # zugewiesen sind (primär oder sekundär). Buchung ohne Team bleibt erlaubt.
    target_mannschaft = mannschaft_override or data.mannschaft or current_user.mannschaft
    if not user_may_book_for(repo, current_user, target_mannschaft):
        errors.append(f"Sie sind für die Mannschaft '{target_mannschaft}' nicht eingetragen.")
        return None, errors

    end_time = compute_end_time(data.start_time, data.duration_min)

    # Konfliktcheck
    conflicts = check_availability(existing_bookings, data.field, data.start_time, data.duration_min)
    if conflicts:
        names = ", ".join(
            f"{_fc.get_display_name(b.field.value)} {b.start_time.strftime('%H:%M')}–{b.end_time.strftime('%H:%M')}"
            for b in conflicts
        )
        errors.append(f"Zeitslot nicht verfügbar. Konflikt mit: {names}")
        return None, errors

    # Sonnenuntergangshinweis für nicht-beleuchtete Felder
    sunset_note = None
    if not _fc.is_lit(data.field.value):
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
        mannschaft=mannschaft_override or data.mannschaft or current_user.mannschaft,
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

    # Sonnenuntergangshinweis für nicht-beleuchtete Felder
    sunset_note = None
    if not _fc.is_lit(data.field.value):
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
