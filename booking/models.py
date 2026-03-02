from __future__ import annotations

from datetime import date, time
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class FieldName(str, Enum):
    # Stabile interne IDs — Anzeigenamen kommen aus config/field_config.json
    A  = "A"   # Kura Ganz (Kunstrasen, ganzer Platz)
    AA = "AA"  # Kura Halb A
    AB = "AB"  # Kura Halb B
    B  = "B"   # Rasen Ganz (Naturrasen, ganzer Platz)
    BA = "BA"  # Rasen Halb A
    BB = "BB"  # Rasen Halb B
    C  = "C"   # Halle Ganz
    CA = "CA"  # Halle 2/3
    CB = "CB"  # Halle 1/3


class BookingStatus(str, Enum):
    BESTAETIGT = "Bestätigt"
    STORNIERT = "Storniert"
    STORNIERT_DFBNET = "Storniert (DFBnet)"


class BookingType(str, Enum):
    TRAINING = "Training"
    SPIEL = "Spiel"
    TURNIER = "Turnier"


class UserRole(str, Enum):
    TRAINER = "Trainer"
    ADMINISTRATOR = "Administrator"
    PLATZWART = "Platzwart"
    DFBNET = "DFBnet"


class Permission(str, Enum):
    # Nutzerverwaltung
    MANAGE_USERS        = "manage_users"        # anlegen, löschen, Passwort-Reset
    # Admin-Dashboard
    ACCESS_ADMIN        = "access_admin"
    # Platzbuchungen
    CREATE_BOOKING      = "create_booking"
    DELETE_OWN_BOOKING  = "delete_own_booking"
    DELETE_ALL_BOOKINGS = "delete_all_bookings"
    # Externe Termine
    CREATE_EVENT        = "create_event"
    DELETE_OWN_EVENT    = "delete_own_event"
    DELETE_ALL_EVENTS   = "delete_all_events"
    # Aufgaben / Meldungen
    CREATE_TASK         = "create_task"
    DELETE_OWN_TASK     = "delete_own_task"
    DELETE_ALL_TASKS    = "delete_all_tasks"
    # Serien
    MANAGE_SERIES       = "manage_series"
    # DFBnet
    DFBNET_SPIELPLAN    = "dfbnet_spielplan"    # Spielplan abrufen / CSV-Import
    DFBNET_BOOKING      = "dfbnet_booking"      # manuelle DFBnet-Buchung


ROLE_PERMISSIONS: dict["UserRole", frozenset["Permission"]] = {
    UserRole.ADMINISTRATOR: frozenset(Permission),  # alles
    UserRole.DFBNET: frozenset({
        Permission.ACCESS_ADMIN,
        Permission.CREATE_BOOKING,
        Permission.DELETE_OWN_BOOKING,
        Permission.CREATE_EVENT,
        Permission.DELETE_OWN_EVENT,
        Permission.CREATE_TASK,
        Permission.DELETE_OWN_TASK,
        Permission.MANAGE_SERIES,
        Permission.DFBNET_SPIELPLAN,
        Permission.DFBNET_BOOKING,
    }),
    UserRole.PLATZWART: frozenset({
        Permission.ACCESS_ADMIN,
        Permission.CREATE_BOOKING,
        Permission.DELETE_OWN_BOOKING,
        Permission.CREATE_EVENT,
        Permission.DELETE_OWN_EVENT,
        Permission.CREATE_TASK,
        Permission.DELETE_OWN_TASK,
        Permission.DELETE_ALL_TASKS,
    }),
    UserRole.TRAINER: frozenset({
        Permission.CREATE_BOOKING,
        Permission.DELETE_OWN_BOOKING,
        Permission.CREATE_EVENT,
        Permission.DELETE_OWN_EVENT,
        Permission.CREATE_TASK,
        Permission.DELETE_OWN_TASK,
    }),
}


def has_permission(role: "UserRole", permission: "Permission") -> bool:
    """Prüft ob eine Rolle eine bestimmte Berechtigung hat."""
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


class SeriesRhythm(str, Enum):
    WOECHENTLICH = "Wöchentlich"
    VIERZEHNTAGIG = "14-tägig"


class SeriesStatus(str, Enum):
    AKTIV = "Aktiv"
    PAUSIERT = "Pausiert"
    BEENDET = "Beendet"


class SeriesSaison(str, Enum):
    GANZJAEHRIG    = "Ganzjährig"
    SOMMERHALBJAHR = "Sommerhalbjahr"
    WINTERHALBJAHR = "Winterhalbjahr"


class MannschaftConfig(BaseModel):
    """Mannschafts-Konfiguration aus der Notion-Teams-DB."""
    notion_id: str
    name: str
    trainer_name: Optional[str] = None
    trainer_id: Optional[str] = None
    fussball_de_team_id: Optional[str] = None
    aktiv: bool = True


# --- Booking ---

class Booking(BaseModel):
    notion_id: str
    title: str
    field: FieldName
    date: date
    start_time: time
    end_time: time
    duration_min: int
    booking_type: BookingType
    booked_by_id: str        # Notion page ID des Nutzers
    booked_by_name: str
    role: UserRole
    status: BookingStatus
    mannschaft: Optional[str] = None
    zweck: Optional[str] = None     # Freitext-Buchungszweck (sichtbar im Kalender)
    kontakt: Optional[str] = None   # Ansprechpartner / Kontaktinfo
    series_id: Optional[str] = None
    series_exception: bool = False
    sunset_note: Optional[str] = None
    spielkennung: Optional[str] = None  # DFBnet-Spielkennung für Duplikaterkennung


class BookingCreate(BaseModel):
    field: FieldName
    date: date
    start_time: time
    duration_min: int
    booking_type: BookingType
    zweck: Optional[str] = None
    kontakt: Optional[str] = None
    spielkennung: Optional[str] = None


# --- Series ---

class Series(BaseModel):
    notion_id: str
    title: str
    field: FieldName
    start_time: time
    duration_min: int
    rhythm: SeriesRhythm
    start_date: date
    end_date: date
    booked_by_id: str
    booked_by_name: str
    status: SeriesStatus
    mannschaft: Optional[str] = None
    trainer_id: Optional[str] = None
    trainer_name: Optional[str] = None
    saison: SeriesSaison = SeriesSaison.GANZJAEHRIG


class SeriesCreate(BaseModel):
    field: FieldName
    start_time: time
    duration_min: int
    rhythm: SeriesRhythm
    start_date: date
    end_date: date
    mannschaft: str
    trainer_id: str
    saison: SeriesSaison = SeriesSaison.GANZJAEHRIG


# --- User ---

class User(BaseModel):
    notion_id: str
    name: str
    role: UserRole
    email: str
    password_hash: str
    mannschaft: Optional[str] = None
    must_change_password: bool = False


class UserCreate(BaseModel):
    name: str
    role: UserRole
    email: str
    password: str
    mannschaft: Optional[str] = None


# --- Aufgaben / Schwarzes Brett ---

class AufgabeTyp(str, Enum):
    DEFEKT = "Defekt"
    NUTZERANFRAGE = "Nutzeranfrage"
    TURNIERTERMIN = "Turniertermin"
    SONSTIGES = "Sonstiges"


class AufgabeStatus(str, Enum):
    OFFEN = "Offen"
    IN_BEARBEITUNG = "In Bearbeitung"
    ERLEDIGT = "Erledigt"


class Prioritaet(str, Enum):
    NIEDRIG = "Niedrig"
    MITTEL = "Mittel"
    HOCH = "Hoch"


class Aufgabe(BaseModel):
    notion_id: str
    titel: str
    typ: AufgabeTyp
    status: AufgabeStatus
    prioritaet: Prioritaet
    erstellt_von_id: str
    erstellt_von_name: str
    erstellt_am: date
    faellig_am: Optional[date] = None
    ort: Optional[str] = None           # z. B. "Kura Tor A", "Umkleide 2"
    beschreibung: Optional[str] = None


class AufgabeCreate(BaseModel):
    titel: str
    typ: AufgabeTyp
    prioritaet: Prioritaet = Prioritaet.MITTEL
    faellig_am: Optional[date] = None
    ort: Optional[str] = None
    beschreibung: Optional[str] = None


# --- Externe Events (keine Platzbuchung) ---

class ExternalEvent(BaseModel):
    notion_id: str
    title: str
    date: date
    start_time: time
    location: Optional[str] = None
    description: Optional[str] = None
    created_by_id: str
    created_by_name: str
    mannschaft: Optional[str] = None   # Team, dem der Termin zugeordnet ist


class ExternalEventCreate(BaseModel):
    title: str
    date: date
    start_time: time
    location: Optional[str] = None
    description: Optional[str] = None
    mannschaft: Optional[str] = None   # Team, dem der Termin zugeordnet ist


# JWT token payload (kein Pydantic-Model, nur TypedDict-ähnlich)
class TokenPayload(BaseModel):
    sub: str        # notion_id des Nutzers
    username: str
    role: UserRole
    mannschaft: Optional[str] = None
    must_change_password: bool = False
    exp: int
    iat: int = 0    # issued-at (Unix-Timestamp) für Invalidierung
