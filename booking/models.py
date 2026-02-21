from __future__ import annotations

from datetime import date, time
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class FieldName(str, Enum):
    KURA_GANZ = "Kura Ganz"
    KURA_HALB_A = "Kura Halb A"
    KURA_HALB_B = "Kura Halb B"
    RASEN_GANZ = "Rasen Ganz"
    RASEN_HALB_A = "Rasen Halb A"
    RASEN_HALB_B = "Rasen Halb B"
    HALLE_GANZ = "Halle Ganz"
    HALLE_ZWEIDRITTEL = "Halle 2/3"
    HALLE_EINDRITTEL = "Halle 1/3"

    @property
    def is_rasen(self) -> bool:
        return self.value.startswith("Rasen")

    @property
    def is_kura(self) -> bool:
        return self.value.startswith("Kura")

    @property
    def is_halle(self) -> bool:
        return self.value.startswith("Halle")

    @property
    def is_ganz(self) -> bool:
        return self.value.endswith("Ganz")


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
    # Sperrzeiten & Serien
    MANAGE_BLACKOUTS    = "manage_blackouts"
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
        Permission.MANAGE_BLACKOUTS,
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


class BlackoutType(str, Enum):
    GANZTAEGIG = "Ganztägig"
    ZEITLICH = "Zeitlich"


class Mannschaft(str, Enum):
    G1 = "G1"
    G2 = "G2"
    G3 = "G3"
    F1 = "F1"
    F2 = "F2"
    E1 = "E1"
    E2 = "E2"
    E3 = "E3"
    D1 = "D1"
    D2 = "D2"
    C = "C"
    B = "B"
    A = "A"
    TUS1 = "TuS 1"
    TUS2 = "TuS 2"
    UE32 = "Ü32"
    UE40 = "Ü40"
    FRAUEN = "Frauen"
    MAEDCHEN = "Mädchen"


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


class SeriesCreate(BaseModel):
    field: FieldName
    start_time: time
    duration_min: int
    rhythm: SeriesRhythm
    start_date: date
    end_date: date
    mannschaft: Mannschaft
    trainer_id: str


# --- Blackout ---

class BlackoutPeriod(BaseModel):
    notion_id: str
    title: str
    start_date: date
    end_date: date
    blackout_type: BlackoutType
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    reason: str
    entered_by_id: str
    entered_by_name: str


class BlackoutCreate(BaseModel):
    start_date: date
    end_date: date
    blackout_type: BlackoutType
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    reason: str


# --- User ---

class User(BaseModel):
    notion_id: str
    name: str
    role: UserRole
    email: str
    password_hash: str
    mannschaft: Optional[Mannschaft] = None
    must_change_password: bool = False


class UserCreate(BaseModel):
    name: str
    role: UserRole
    email: str
    password: str
    mannschaft: Optional[Mannschaft] = None


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
