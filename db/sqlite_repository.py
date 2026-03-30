"""SQLite-Implementierung des AbstractRepository.

Nutzt die stdlib `sqlite3` (synchron) — FastAPI-Router rufen die Methoden
per `asyncio.get_event_loop().run_in_executor(None, ...)` auf, falls nötig.
Da die App aktuell die Repository-Methoden direkt (synchron) aufruft, ist
das hier transparent nutzbar.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from datetime import date, time
from typing import Optional

from booking.models import (
    Aufgabe,
    AufgabeCreate,
    AufgabeStatus,
    AufgabeTyp,
    BlackoutCreate,
    BlackoutPeriod,
    BlackoutType,
    Booking,
    BookingCreate,
    BookingStatus,
    BookingType,
    ExternalEvent,
    ExternalEventCreate,
    FieldName,
    MannschaftConfig,
    Prioritaet,
    Series,
    SeriesCreate,
    SeriesRhythm,
    SeriesSaison,
    SeriesStatus,
    User,
    UserCreate,
    UserRole,
)
from db.repository import AbstractRepository

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def _parse_time(value: Optional[str]) -> Optional[time]:
    if not value:
        return None
    h, m = value.split(":")
    return time(int(h), int(m))


def _fmt_time(value: Optional[time]) -> Optional[str]:
    if value is None:
        return None
    return value.strftime("%H:%M")


def _fmt_date(value: Optional[date]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


class SQLiteRepository(AbstractRepository):
    """Repository-Implementierung auf Basis von SQLite (stdlib sqlite3)."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._local = threading.local()
        # Initialisierung: Schema einmalig auf der Haupt-Verbindung anwenden
        conn = self._get_conn()
        conn.executescript(open(_SCHEMA_PATH, encoding="utf-8").read())
        conn.commit()
        # Migration: cc_emails column (added later)
        try:
            conn.execute(
                "ALTER TABLE mannschaften ADD COLUMN cc_emails TEXT NOT NULL DEFAULT ''"
            )
            conn.commit()
        except Exception:
            pass  # column already exists
        # Migration: shortname column
        try:
            conn.execute("ALTER TABLE mannschaften ADD COLUMN shortname TEXT")
            conn.commit()
        except Exception:
            pass  # column already exists

    def _get_conn(self) -> sqlite3.Connection:
        """Gibt eine thread-lokale Datenbankverbindung zurück."""
        if not getattr(self._local, "conn", None):
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    # ------------------------------------------------------------------ helpers

    def _new_id(self) -> str:
        return str(uuid.uuid4())

    # ------------------------------------------------------------------ user

    def _row_to_user(self, row: sqlite3.Row) -> User:
        return User(
            notion_id=row["id"],
            name=row["name"],
            role=UserRole(row["role"]),
            email=row["email"] or "",
            password_hash=row["password_hash"] or "",
            mannschaft=row["mannschaft"] or None,
            must_change_password=bool(row["must_change_pw"]),
        )

    def get_user_by_name(self, name: str) -> Optional[User]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM users WHERE name = ? AND deleted_at IS NULL",
            (name,),
        ).fetchone()
        return self._row_to_user(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM users WHERE id = ? AND deleted_at IS NULL",
            (user_id,),
        ).fetchone()
        return self._row_to_user(row) if row else None

    def create_user(self, user: UserCreate, password_hash: str) -> User:
        conn = self._get_conn()
        new_id = self._new_id()
        conn.execute(
            """
            INSERT INTO users (id, name, role, email, password_hash, mannschaft, must_change_pw)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (new_id, user.name, user.role.value, user.email, password_hash, user.mannschaft),
        )
        conn.commit()
        return self.get_user_by_id(new_id)  # type: ignore[return-value]

    def update_user_password(self, user_id: str, password_hash: str) -> User:
        conn = self._get_conn()
        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_pw = 0 WHERE id = ?",
            (password_hash, user_id),
        )
        conn.commit()
        return self.get_user_by_id(user_id)  # type: ignore[return-value]

    def reset_user_password(self, user_id: str, password_hash: str) -> User:
        conn = self._get_conn()
        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_pw = 1 WHERE id = ?",
            (password_hash, user_id),
        )
        conn.commit()
        return self.get_user_by_id(user_id)  # type: ignore[return-value]

    def update_user(
        self, user_id: str, role: str, email: str, mannschaft: Optional[str]
    ) -> User:
        conn = self._get_conn()
        conn.execute(
            "UPDATE users SET role = ?, email = ?, mannschaft = ? WHERE id = ?",
            (role, email, mannschaft, user_id),
        )
        conn.commit()
        return self.get_user_by_id(user_id)  # type: ignore[return-value]

    def delete_user(self, user_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE users SET deleted_at = ? WHERE id = ?",
            (date.today().isoformat(), user_id),
        )
        conn.commit()

    def get_all_users(self) -> list[User]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM users WHERE deleted_at IS NULL ORDER BY name"
        ).fetchall()
        return [self._row_to_user(r) for r in rows]

    def get_trainers_for_mannschaft(self, mannschaft: str) -> list[User]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM users WHERE mannschaft = ? AND role = ? AND deleted_at IS NULL",
            (mannschaft, UserRole.TRAINER.value),
        ).fetchall()
        return [self._row_to_user(r) for r in rows]

    # ------------------------------------------------------------------ booking

    def _row_to_booking(self, row: sqlite3.Row) -> Booking:
        return Booking(
            notion_id=row["id"],
            title=row["title"],
            field=FieldName(row["field"]),
            date=date.fromisoformat(row["date"]),
            start_time=_parse_time(row["start_time"]),  # type: ignore[arg-type]
            end_time=_parse_time(row["end_time"]),  # type: ignore[arg-type]
            duration_min=row["duration_min"],
            booking_type=BookingType(row["booking_type"]),
            booked_by_id=row["booked_by_id"],
            booked_by_name=row["booked_by_name"],
            role=UserRole(row["role"]),
            status=BookingStatus(row["status"]),
            mannschaft=row["mannschaft"] or None,
            zweck=row["zweck"] or None,
            kontakt=row["kontakt"] or None,
            series_id=row["series_id"] or None,
            series_exception=bool(row["series_exception"]),
            sunset_note=row["sunset_note"] or None,
            spielkennung=row["spielkennung"] or None,
        )

    def get_bookings_for_date(self, booking_date: date) -> list[Booking]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM bookings WHERE date = ? AND status = ? ORDER BY start_time",
            (booking_date.isoformat(), BookingStatus.BESTAETIGT.value),
        ).fetchall()
        return [self._row_to_booking(r) for r in rows]

    def get_bookings_for_week(self, year: int, week: int) -> list[Booking]:
        monday = date.fromisocalendar(year, week, 1)
        sunday = date.fromisocalendar(year, week, 7)
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM bookings
            WHERE date >= ? AND date <= ? AND status = ?
            ORDER BY date, start_time
            """,
            (monday.isoformat(), sunday.isoformat(), BookingStatus.BESTAETIGT.value),
        ).fetchall()
        return [self._row_to_booking(r) for r in rows]

    def get_bookings_for_series(
        self, series_id: str, only_future: bool = False
    ) -> list[Booking]:
        conn = self._get_conn()
        if only_future:
            rows = conn.execute(
                """
                SELECT * FROM bookings
                WHERE series_id = ? AND status = ? AND series_exception = 0
                  AND date >= ?
                ORDER BY date
                """,
                (series_id, BookingStatus.BESTAETIGT.value, date.today().isoformat()),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM bookings
                WHERE series_id = ? AND status = ? AND series_exception = 0
                ORDER BY date
                """,
                (series_id, BookingStatus.BESTAETIGT.value),
            ).fetchall()
        return [self._row_to_booking(r) for r in rows]

    def get_booking_by_id(self, booking_id: str) -> Optional[Booking]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM bookings WHERE id = ?", (booking_id,)
        ).fetchone()
        return self._row_to_booking(row) if row else None

    def get_upcoming_games(self, limit: int = 10) -> list[Booking]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM bookings
            WHERE booking_type = ? AND status = ? AND date >= ?
            ORDER BY date, start_time
            LIMIT ?
            """,
            (
                BookingType.SPIEL.value,
                BookingStatus.BESTAETIGT.value,
                date.today().isoformat(),
                limit,
            ),
        ).fetchall()
        return [self._row_to_booking(r) for r in rows]

    def get_bookings_by_spielkennung(
        self, kennungen: list[str]
    ) -> dict[str, Booking]:
        if not kennungen:
            return {}
        conn = self._get_conn()
        placeholders = ",".join("?" * len(kennungen))
        rows = conn.execute(
            f"""
            SELECT * FROM bookings
            WHERE spielkennung IN ({placeholders}) AND status = ?
            """,
            (*kennungen, BookingStatus.BESTAETIGT.value),
        ).fetchall()
        return {r["spielkennung"]: self._row_to_booking(r) for r in rows}

    def get_bookings_in_range(self, start: date, end: date) -> list[Booking]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM bookings
            WHERE date >= ? AND date <= ? AND status = ?
            ORDER BY date, start_time
            """,
            (start.isoformat(), end.isoformat(), BookingStatus.BESTAETIGT.value),
        ).fetchall()
        return [self._row_to_booking(r) for r in rows]

    def get_all_bookings(self, from_date: Optional[date] = None) -> list[Booking]:
        conn = self._get_conn()
        start = from_date or date.today()
        rows = conn.execute(
            """
            SELECT * FROM bookings
            WHERE date >= ? AND status = ?
            ORDER BY date, start_time
            """,
            (start.isoformat(), BookingStatus.BESTAETIGT.value),
        ).fetchall()
        return [self._row_to_booking(r) for r in rows]

    def create_booking(
        self,
        data: BookingCreate,
        booked_by_id: str,
        booked_by_name: str,
        role: UserRole,
        end_time: time,
        sunset_note: Optional[str] = None,
        series_id: Optional[str] = None,
        mannschaft: Optional[str] = None,
        zweck: Optional[str] = None,
        kontakt: Optional[str] = None,
    ) -> Booking:
        conn = self._get_conn()
        new_id = self._new_id()
        title = (
            f"{data.field.value} – "
            f"{data.date.isoformat()} "
            f"{data.start_time.strftime('%H:%M')}"
        )
        conn.execute(
            """
            INSERT INTO bookings (
                id, title, field, date, start_time, end_time, duration_min,
                booking_type, booked_by_id, booked_by_name, role, status,
                mannschaft, zweck, kontakt, series_id, series_exception,
                sunset_note, spielkennung
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                new_id, title, data.field.value, data.date.isoformat(),
                data.start_time.strftime("%H:%M"), end_time.strftime("%H:%M"),
                data.duration_min, data.booking_type.value,
                booked_by_id, booked_by_name, role.value,
                BookingStatus.BESTAETIGT.value,
                mannschaft, zweck or data.zweck, kontakt or data.kontakt,
                series_id, sunset_note, data.spielkennung,
            ),
        )
        conn.commit()
        return self.get_booking_by_id(new_id)  # type: ignore[return-value]

    def update_booking_status(
        self, booking_id: str, status: BookingStatus
    ) -> Booking:
        conn = self._get_conn()
        conn.execute(
            "UPDATE bookings SET status = ? WHERE id = ?",
            (status.value, booking_id),
        )
        conn.commit()
        return self.get_booking_by_id(booking_id)  # type: ignore[return-value]

    def mark_series_exception(self, booking_id: str) -> Booking:
        conn = self._get_conn()
        conn.execute(
            "UPDATE bookings SET status = ?, series_exception = 1 WHERE id = ?",
            (BookingStatus.STORNIERT.value, booking_id),
        )
        conn.commit()
        return self.get_booking_by_id(booking_id)  # type: ignore[return-value]

    def enrich_booking(
        self,
        booking_id: str,
        mannschaft: Optional[str] = None,
        spielkennung: Optional[str] = None,
    ) -> None:
        if not mannschaft and not spielkennung:
            return
        conn = self._get_conn()
        if mannschaft and spielkennung:
            conn.execute(
                "UPDATE bookings SET mannschaft = ?, spielkennung = ? WHERE id = ?",
                (mannschaft, spielkennung, booking_id),
            )
        elif mannschaft:
            conn.execute(
                "UPDATE bookings SET mannschaft = ? WHERE id = ?",
                (mannschaft, booking_id),
            )
        else:
            conn.execute(
                "UPDATE bookings SET spielkennung = ? WHERE id = ?",
                (spielkennung, booking_id),
            )
        conn.commit()

    # ------------------------------------------------------------------ series

    def _row_to_series(self, row: sqlite3.Row) -> Series:
        try:
            saison = SeriesSaison(row["saison"])
        except ValueError:
            saison = SeriesSaison.GANZJAEHRIG
        return Series(
            notion_id=row["id"],
            title=row["title"],
            field=FieldName(row["field"]),
            start_time=_parse_time(row["start_time"]),  # type: ignore[arg-type]
            duration_min=row["duration_min"],
            rhythm=SeriesRhythm(row["rhythm"]),
            start_date=date.fromisoformat(row["start_date"]),
            end_date=date.fromisoformat(row["end_date"]),
            booked_by_id=row["booked_by_id"],
            booked_by_name=row["booked_by_name"],
            status=SeriesStatus(row["status"]),
            mannschaft=row["mannschaft"] or None,
            trainer_id=row["trainer_id"] or None,
            trainer_name=row["trainer_name"] or None,
            saison=saison,
        )

    def get_all_series(self, only_active: bool = False) -> list[Series]:
        conn = self._get_conn()
        if only_active:
            rows = conn.execute(
                "SELECT * FROM series WHERE status = ? ORDER BY start_date DESC",
                (SeriesStatus.AKTIV.value,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM series ORDER BY start_date DESC"
            ).fetchall()
        return [self._row_to_series(r) for r in rows]

    def get_series_by_id(self, series_id: str) -> Optional[Series]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM series WHERE id = ?", (series_id,)
        ).fetchone()
        return self._row_to_series(row) if row else None

    def create_series(
        self,
        data: SeriesCreate,
        booked_by_id: str,
        booked_by_name: str,
        trainer_name: str,
    ) -> Series:
        conn = self._get_conn()
        new_id = self._new_id()
        title = (
            f"Serie {data.mannschaft} {data.field.value} "
            f"{data.start_time.strftime('%H:%M')} "
            f"ab {data.start_date.isoformat()}"
        )
        conn.execute(
            """
            INSERT INTO series (
                id, title, field, start_time, duration_min, rhythm,
                start_date, end_date, booked_by_id, booked_by_name,
                status, mannschaft, trainer_id, trainer_name, saison
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id, title, data.field.value,
                data.start_time.strftime("%H:%M"), data.duration_min,
                data.rhythm.value, data.start_date.isoformat(),
                data.end_date.isoformat(), booked_by_id, booked_by_name,
                SeriesStatus.AKTIV.value, data.mannschaft,
                data.trainer_id, trainer_name, data.saison.value,
            ),
        )
        conn.commit()
        return self.get_series_by_id(new_id)  # type: ignore[return-value]

    def update_series_status(
        self, series_id: str, status: SeriesStatus
    ) -> Series:
        conn = self._get_conn()
        conn.execute(
            "UPDATE series SET status = ? WHERE id = ?",
            (status.value, series_id),
        )
        conn.commit()
        return self.get_series_by_id(series_id)  # type: ignore[return-value]

    # ------------------------------------------------------------------ blackouts

    def _row_to_blackout(self, row: sqlite3.Row) -> BlackoutPeriod:
        return BlackoutPeriod(
            notion_id=row["id"],
            title=row["title"],
            start_date=date.fromisoformat(row["start_date"]),
            end_date=date.fromisoformat(row["end_date"]),
            blackout_type=BlackoutType(row["blackout_type"]),
            start_time=_parse_time(row["start_time"]),
            end_time=_parse_time(row["end_time"]),
            reason=row["reason"] or "",
            entered_by_id=row["entered_by_id"],
            entered_by_name=row["entered_by_name"],
        )

    def get_blackouts_for_date(self, blackout_date: date) -> list[BlackoutPeriod]:
        conn = self._get_conn()
        d = blackout_date.isoformat()
        rows = conn.execute(
            """
            SELECT * FROM blackouts
            WHERE start_date <= ? AND end_date >= ? AND deleted_at IS NULL
            ORDER BY start_date
            """,
            (d, d),
        ).fetchall()
        return [self._row_to_blackout(r) for r in rows]

    def get_blackouts_for_week(self, year: int, week: int) -> list[BlackoutPeriod]:
        monday = date.fromisocalendar(year, week, 1)
        sunday = date.fromisocalendar(year, week, 7)
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM blackouts
            WHERE start_date <= ? AND end_date >= ? AND deleted_at IS NULL
            ORDER BY start_date
            """,
            (sunday.isoformat(), monday.isoformat()),
        ).fetchall()
        return [self._row_to_blackout(r) for r in rows]

    def get_all_blackouts(self) -> list[BlackoutPeriod]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM blackouts WHERE deleted_at IS NULL ORDER BY start_date DESC"
        ).fetchall()
        return [self._row_to_blackout(r) for r in rows]

    def create_blackout(
        self,
        data: BlackoutCreate,
        entered_by_id: str,
        entered_by_name: str,
    ) -> BlackoutPeriod:
        conn = self._get_conn()
        new_id = self._new_id()
        conn.execute(
            """
            INSERT INTO blackouts (
                id, title, start_date, end_date, blackout_type,
                start_time, end_time, reason, entered_by_id, entered_by_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id, data.title,
                data.start_date.isoformat(), data.end_date.isoformat(),
                data.blackout_type.value,
                _fmt_time(data.start_time), _fmt_time(data.end_time),
                data.reason, entered_by_id, entered_by_name,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM blackouts WHERE id = ?", (new_id,)
        ).fetchone()
        return self._row_to_blackout(row)

    def delete_blackout(self, blackout_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE blackouts SET deleted_at = ? WHERE id = ?",
            (date.today().isoformat(), blackout_id),
        )
        conn.commit()

    # ------------------------------------------------------------------ aufgaben

    def _row_to_aufgabe(self, row: sqlite3.Row) -> Aufgabe:
        return Aufgabe(
            notion_id=row["id"],
            titel=row["titel"],
            typ=AufgabeTyp(row["typ"]),
            status=AufgabeStatus(row["status"]),
            prioritaet=Prioritaet(row["prioritaet"]),
            erstellt_von_id=row["erstellt_von_id"],
            erstellt_von_name=row["erstellt_von_name"],
            erstellt_am=date.fromisoformat(row["erstellt_am"]),
            faellig_am=date.fromisoformat(row["faellig_am"]) if row["faellig_am"] else None,
            ort=row["ort"] or None,
            beschreibung=row["beschreibung"] or None,
        )

    def get_all_aufgaben(self, only_open: bool = False) -> list[Aufgabe]:
        conn = self._get_conn()
        if only_open:
            rows = conn.execute(
                """
                SELECT * FROM aufgaben
                WHERE status != ? AND deleted_at IS NULL
                ORDER BY erstellt_am DESC
                """,
                (AufgabeStatus.ERLEDIGT.value,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM aufgaben WHERE deleted_at IS NULL ORDER BY erstellt_am DESC"
            ).fetchall()
        return [self._row_to_aufgabe(r) for r in rows]

    def get_aufgabe_by_id(self, aufgabe_id: str) -> Optional[Aufgabe]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM aufgaben WHERE id = ? AND deleted_at IS NULL",
            (aufgabe_id,),
        ).fetchone()
        return self._row_to_aufgabe(row) if row else None

    def create_aufgabe(
        self,
        data: AufgabeCreate,
        created_by_id: str,
        created_by_name: str,
    ) -> Aufgabe:
        conn = self._get_conn()
        new_id = self._new_id()
        conn.execute(
            """
            INSERT INTO aufgaben (
                id, titel, typ, status, prioritaet,
                erstellt_von_id, erstellt_von_name, erstellt_am,
                faellig_am, ort, beschreibung
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id, data.titel, data.typ.value,
                AufgabeStatus.OFFEN.value, data.prioritaet.value,
                created_by_id, created_by_name, date.today().isoformat(),
                _fmt_date(data.faellig_am), data.ort, data.beschreibung,
            ),
        )
        conn.commit()
        return self.get_aufgabe_by_id(new_id)  # type: ignore[return-value]

    def update_aufgabe_status(
        self, aufgabe_id: str, status: AufgabeStatus
    ) -> Aufgabe:
        conn = self._get_conn()
        conn.execute(
            "UPDATE aufgaben SET status = ? WHERE id = ?",
            (status.value, aufgabe_id),
        )
        conn.commit()
        return self.get_aufgabe_by_id(aufgabe_id)  # type: ignore[return-value]

    def delete_aufgabe(self, aufgabe_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE aufgaben SET deleted_at = ? WHERE id = ?",
            (date.today().isoformat(), aufgabe_id),
        )
        conn.commit()

    # ------------------------------------------------------------------ events

    def _row_to_event(self, row: sqlite3.Row) -> ExternalEvent:
        return ExternalEvent(
            notion_id=row["id"],
            title=row["title"],
            date=date.fromisoformat(row["date"]),
            start_time=_parse_time(row["start_time"]) or time(0, 0),  # type: ignore[arg-type]
            location=row["location"] or None,
            description=row["description"] or None,
            created_by_id=row["created_by_id"],
            created_by_name=row["created_by_name"],
            mannschaft=row["mannschaft"] or None,
        )

    def get_upcoming_events(self, limit: int = 10) -> list[ExternalEvent]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM events
            WHERE date >= ? AND deleted_at IS NULL
            ORDER BY date, start_time
            LIMIT ?
            """,
            (date.today().isoformat(), limit),
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def get_all_events(self) -> list[ExternalEvent]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM events WHERE deleted_at IS NULL ORDER BY date DESC, start_time DESC"
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def get_event_by_id(self, event_id: str) -> Optional[ExternalEvent]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM events WHERE id = ? AND deleted_at IS NULL",
            (event_id,),
        ).fetchone()
        return self._row_to_event(row) if row else None

    def create_event(
        self, data: ExternalEventCreate, user_id: str, user_name: str
    ) -> ExternalEvent:
        conn = self._get_conn()
        new_id = self._new_id()
        conn.execute(
            """
            INSERT INTO events (
                id, title, date, start_time, location,
                description, created_by_id, created_by_name, mannschaft
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id, data.title, data.date.isoformat(),
                data.start_time.strftime("%H:%M"),
                data.location, data.description,
                user_id, user_name, data.mannschaft,
            ),
        )
        conn.commit()
        return self.get_event_by_id(new_id)  # type: ignore[return-value]

    def delete_event(self, event_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE events SET deleted_at = ? WHERE id = ?",
            (date.today().isoformat(), event_id),
        )
        conn.commit()

    # ------------------------------------------------------------------ mannschaften

    def _row_to_mannschaft(self, row: sqlite3.Row) -> MannschaftConfig:
        return MannschaftConfig(
            notion_id=row["id"],
            name=row["name"],
            shortname=row["shortname"] or None,
            trainer_name=row["trainer_name"] or None,
            trainer_id=row["trainer_id"] or None,
            fussball_de_team_id=row["fussball_de_team_id"] or None,
            aktiv=bool(row["aktiv"]),
            cc_emails=[e.strip() for e in (row["cc_emails"] or "").split(",") if e.strip()],
        )

    def get_all_mannschaften(self, only_active: bool = False) -> list[MannschaftConfig]:
        conn = self._get_conn()
        if only_active:
            rows = conn.execute(
                "SELECT * FROM mannschaften WHERE aktiv = 1 ORDER BY name"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM mannschaften ORDER BY name"
            ).fetchall()
        return [self._row_to_mannschaft(r) for r in rows]

    def get_mannschaft_by_id(self, mannschaft_id: str) -> Optional[MannschaftConfig]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM mannschaften WHERE id = ?", (mannschaft_id,)
        ).fetchone()
        return self._row_to_mannschaft(row) if row else None

    def create_mannschaft(
        self,
        name: str,
        trainer_id: Optional[str],
        trainer_name: Optional[str],
        fussball_de_team_id: Optional[str],
        cc_emails: list[str],
        aktiv: bool = True,
        shortname: Optional[str] = None,
    ) -> MannschaftConfig:
        mid = str(uuid.uuid4())
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO mannschaften (id, name, shortname, trainer_name, trainer_id, fussball_de_team_id, aktiv, cc_emails) VALUES (?,?,?,?,?,?,?,?)",
            (mid, name, shortname, trainer_name, trainer_id, fussball_de_team_id, 1 if aktiv else 0, ",".join(cc_emails)),
        )
        conn.commit()
        return self.get_mannschaft_by_id(mid)  # type: ignore[return-value]

    def update_mannschaft(
        self,
        mannschaft_id: str,
        name: str,
        trainer_id: Optional[str],
        trainer_name: Optional[str],
        fussball_de_team_id: Optional[str],
        cc_emails: list[str],
        aktiv: bool,
        shortname: Optional[str] = None,
    ) -> MannschaftConfig:
        conn = self._get_conn()
        conn.execute(
            "UPDATE mannschaften SET name=?, shortname=?, trainer_name=?, trainer_id=?, fussball_de_team_id=?, aktiv=?, cc_emails=? WHERE id=?",
            (name, shortname, trainer_name, trainer_id, fussball_de_team_id, 1 if aktiv else 0, ",".join(cc_emails), mannschaft_id),
        )
        conn.commit()
        return self.get_mannschaft_by_id(mannschaft_id)  # type: ignore[return-value]

    def delete_mannschaft(self, mannschaft_id: str) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM mannschaften WHERE id = ?", (mannschaft_id,))
        conn.commit()
