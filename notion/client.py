from __future__ import annotations

from datetime import date, time
from typing import Any, Optional

from notion_client import Client

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
    Prioritaet,
    Series,
    SeriesCreate,
    SeriesRhythm,
    SeriesStatus,
    User,
    UserCreate,
    UserRole,
)
from web.config import Settings


def _title(value: str) -> dict:
    return {"title": [{"text": {"content": value}}]}


def _select(value: str) -> dict:
    return {"select": {"name": value}}


def _date_prop(value: date) -> dict:
    return {"date": {"start": value.isoformat()}}


def _rich_text(value: str) -> dict:
    return {"rich_text": [{"text": {"content": value}}]}


def _checkbox(value: bool) -> dict:
    return {"checkbox": value}


def _relation(page_id: str) -> dict:
    return {"relation": [{"id": page_id}]}


def _email(value: str) -> dict:
    return {"email": value}


def _get_title(props: dict, key: str) -> str:
    items = props.get(key, {}).get("title", [])
    return items[0]["plain_text"] if items else ""


def _get_select(props: dict, key: str) -> Optional[str]:
    sel = props.get(key, {}).get("select")
    return sel["name"] if sel else None


def _get_rich_text(props: dict, key: str) -> str:
    items = props.get(key, {}).get("rich_text", [])
    return items[0]["plain_text"] if items else ""


def _get_date(props: dict, key: str) -> Optional[date]:
    d = props.get(key, {}).get("date")
    if d and d.get("start"):
        return date.fromisoformat(d["start"])
    return None


def _get_date_end(props: dict, key: str) -> Optional[date]:
    d = props.get(key, {}).get("date")
    if d and d.get("end"):
        return date.fromisoformat(d["end"])
    return None


def _date_range_prop(start: date, end: date) -> dict:
    return {"date": {"start": start.isoformat(), "end": end.isoformat()}}


def _get_checkbox(props: dict, key: str) -> bool:
    return props.get(key, {}).get("checkbox", False)


def _get_relation_id(props: dict, key: str) -> Optional[str]:
    rel = props.get(key, {}).get("relation", [])
    return rel[0]["id"] if rel else None


def _get_email(props: dict, key: str) -> str:
    return props.get(key, {}).get("email") or ""


def _parse_time(value: Optional[str]) -> Optional[time]:
    if not value:
        return None
    h, m = value.split(":")
    return time(int(h), int(m))


class NotionRepository:
    def __init__(self, settings: Settings) -> None:
        self._client = Client(auth=settings.notion_api_key)
        self._settings = settings
        self._db_props_ensured = False
        self._events_db_ensured = False
        self._ensure_db_properties()

    # Properties, die ggf. nachträglich zur Buchungen-DB hinzugefügt wurden
    _REQUIRED_BUCHUNGEN_PROPS: dict[str, dict] = {
        "Spielkennung": {"rich_text": {}},
        "Zweck": {"rich_text": {}},
        "Kontakt": {"rich_text": {}},
    }

    def _ensure_db_properties(self) -> None:
        """Legt fehlende Properties in der Buchungen-DB an."""
        if self._db_props_ensured:
            return
        try:
            db = self._client.databases.retrieve(self._settings.notion_buchungen_db_id)
            existing = db.get("properties", {})
            missing = {
                name: schema
                for name, schema in self._REQUIRED_BUCHUNGEN_PROPS.items()
                if name not in existing
            }
            if missing:
                self._client.databases.update(
                    database_id=self._settings.notion_buchungen_db_id,
                    properties=missing,
                )
        except Exception:
            pass
        self._db_props_ensured = True

    # Properties für die Events-DB
    _REQUIRED_EVENTS_PROPS: dict[str, dict] = {
        "Datum":             {"date": {}},
        "Startzeit":         {"rich_text": {}},
        "Ort":               {"rich_text": {}},
        "Beschreibung":      {"rich_text": {}},
        "Erstellt von ID":   {"rich_text": {}},
        "Erstellt von Name": {"rich_text": {}},
    }

    def _ensure_events_db_properties(self) -> None:
        """Legt fehlende Properties in der Events-DB an (sofern konfiguriert)."""
        if self._events_db_ensured:
            return
        db_id = self._settings.notion_events_db_id
        if not db_id:
            self._events_db_ensured = True
            return
        try:
            db = self._client.databases.retrieve(db_id)
            existing = db.get("properties", {})
            missing = {
                name: schema
                for name, schema in self._REQUIRED_EVENTS_PROPS.items()
                if name not in existing
            }
            if missing:
                self._client.databases.update(database_id=db_id, properties=missing)
        except Exception:
            pass
        self._events_db_ensured = True

    # ------------------------------------------------------------------ helpers

    def _query_all(
        self,
        database_id: str,
        filter: Optional[dict] = None,
        sorts: Optional[list] = None,
    ) -> list[dict]:
        results: list[dict] = []
        cursor: Optional[str] = None
        while True:
            kwargs: dict[str, Any] = {
                "database_id": database_id,
                "page_size": 100,
            }
            if filter:
                kwargs["filter"] = filter
            if sorts:
                kwargs["sorts"] = sorts
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = self._client.databases.query(**kwargs)
            results.extend(resp["results"])
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        return results

    def _update_page(self, page_id: str, properties: dict) -> dict:
        return self._client.pages.update(page_id=page_id, properties=properties)

    # ------------------------------------------------------------------ user

    def _page_to_user(self, page: dict) -> User:
        props = page["properties"]
        mannschaft_val = _get_select(props, "Mannschaft")
        from booking.models import Mannschaft
        return User(
            notion_id=page["id"],
            name=_get_title(props, "Name"),
            role=UserRole(_get_select(props, "Rolle")),
            email=_get_email(props, "E-Mail"),
            password_hash=_get_rich_text(props, "Password_Hash"),
            mannschaft=Mannschaft(mannschaft_val) if mannschaft_val else None,
            must_change_password=_get_checkbox(props, "Passwort ändern"),
        )

    def get_user_by_name(self, name: str) -> Optional[User]:
        pages = self._query_all(
            self._settings.notion_nutzer_db_id,
            filter={"property": "Name", "title": {"equals": name}},
        )
        return self._page_to_user(pages[0]) if pages else None

    def get_user_by_id(self, notion_id: str) -> Optional[User]:
        try:
            page = self._client.pages.retrieve(page_id=notion_id)
            return self._page_to_user(page)
        except Exception:
            return None

    def create_user(self, user: UserCreate, password_hash: str) -> User:
        page = self._client.pages.create(
            parent={"database_id": self._settings.notion_nutzer_db_id},
            properties={
                "Name": _title(user.name),
                "Rolle": _select(user.role.value),
                "E-Mail": _email(user.email),
                "Password_Hash": _rich_text(password_hash),
                "Passwort ändern": _checkbox(True),
                **( {"Mannschaft": _select(user.mannschaft.value)} if user.mannschaft else {} ),
            },
        )
        return self._page_to_user(page)

    def update_user_password(self, user_id: str, password_hash: str) -> User:
        page = self._update_page(user_id, {
            "Password_Hash": _rich_text(password_hash),
            "Passwort ändern": _checkbox(False),
        })
        return self._page_to_user(page)

    def reset_user_password(self, user_id: str, password_hash: str) -> User:
        page = self._update_page(user_id, {
            "Password_Hash": _rich_text(password_hash),
            "Passwort ändern": _checkbox(True),
        })
        return self._page_to_user(page)

    def get_all_users(self) -> list[User]:
        pages = self._query_all(self._settings.notion_nutzer_db_id)
        return [self._page_to_user(p) for p in pages]

    def get_trainers_for_mannschaft(self, mannschaft: str) -> list[User]:
        pages = self._query_all(
            self._settings.notion_nutzer_db_id,
            filter={
                "and": [
                    {"property": "Mannschaft", "select": {"equals": mannschaft}},
                    {"property": "Rolle", "select": {"equals": UserRole.TRAINER.value}},
                ]
            },
        )
        return [self._page_to_user(p) for p in pages]

    # ------------------------------------------------------------------ booking

    def _page_to_booking(self, page: dict) -> Booking:
        props = page["properties"]
        return Booking(
            notion_id=page["id"],
            title=_get_title(props, "Titel"),
            field=FieldName(_get_select(props, "Platz")),
            date=_get_date(props, "Datum"),
            start_time=_parse_time(_get_select(props, "Startzeit")),
            end_time=_parse_time(_get_select(props, "Endzeit")),
            duration_min=int(_get_select(props, "Dauer") or 60),
            booking_type=BookingType(_get_select(props, "Typ")),
            booked_by_id=_get_rich_text(props, "Gebucht von") or "",
            booked_by_name=_get_rich_text(props, "Gebucht von Name"),
            role=UserRole(_get_select(props, "Rolle")),
            status=BookingStatus(_get_select(props, "Status")),
            mannschaft=_get_rich_text(props, "Mannschaft") or None,
            zweck=_get_rich_text(props, "Zweck") or None,
            kontakt=_get_rich_text(props, "Kontakt") or None,
            series_id=_get_rich_text(props, "Serie") or None,
            series_exception=_get_checkbox(props, "Serienausnahme"),
            sunset_note=_get_rich_text(props, "Hinweis Sonnenuntergang") or None,
            spielkennung=_get_rich_text(props, "Spielkennung") or None,
        )

    def get_bookings_for_date(self, booking_date: date) -> list[Booking]:
        pages = self._query_all(
            self._settings.notion_buchungen_db_id,
            filter={
                "and": [
                    {"property": "Datum", "date": {"equals": booking_date.isoformat()}},
                    {"property": "Status", "select": {"equals": BookingStatus.BESTAETIGT.value}},
                ]
            },
        )
        return [self._page_to_booking(p) for p in pages]

    def get_bookings_for_week(self, year: int, week: int) -> list[Booking]:
        from datetime import timedelta
        monday = date.fromisocalendar(year, week, 1)
        sunday = monday + timedelta(days=6)
        pages = self._query_all(
            self._settings.notion_buchungen_db_id,
            filter={
                "and": [
                    {"property": "Datum", "date": {"on_or_after": monday.isoformat()}},
                    {"property": "Datum", "date": {"on_or_before": sunday.isoformat()}},
                    {"property": "Status", "select": {"equals": BookingStatus.BESTAETIGT.value}},
                ]
            },
            sorts=[{"property": "Datum", "direction": "ascending"}],
        )
        return [self._page_to_booking(p) for p in pages]

    def get_bookings_for_series(self, series_id: str, only_future: bool = False) -> list[Booking]:
        filter_: dict = {
            "and": [
                {"property": "Serie", "rich_text": {"equals": series_id}},
                {"property": "Status", "select": {"equals": BookingStatus.BESTAETIGT.value}},
                {"property": "Serienausnahme", "checkbox": {"equals": False}},
            ]
        }
        if only_future:
            filter_["and"].append(
                {"property": "Datum", "date": {"on_or_after": date.today().isoformat()}}
            )
        pages = self._query_all(self._settings.notion_buchungen_db_id, filter=filter_)
        return [self._page_to_booking(p) for p in pages]

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
        title = (
            f"{data.field.value} – "
            f"{data.date.isoformat()} "
            f"{data.start_time.strftime('%H:%M')}"
        )
        props: dict = {
            "Titel": _title(title),
            "Platz": _select(data.field.value),
            "Datum": _date_prop(data.date),
            "Startzeit": _select(data.start_time.strftime("%H:%M")),
            "Endzeit": _select(end_time.strftime("%H:%M")),
            "Dauer": _select(str(data.duration_min)),
            "Typ": _select(data.booking_type.value),
            "Gebucht von": _rich_text(booked_by_id),
            "Gebucht von Name": _rich_text(booked_by_name),
            "Rolle": _select(role.value),
            "Status": _select(BookingStatus.BESTAETIGT.value),
            "Serienausnahme": _checkbox(False),
        }
        if mannschaft:
            props["Mannschaft"] = _rich_text(mannschaft)
        if zweck:
            props["Zweck"] = _rich_text(zweck)
        if kontakt:
            props["Kontakt"] = _rich_text(kontakt)
        if sunset_note:
            props["Hinweis Sonnenuntergang"] = _rich_text(sunset_note)
        if series_id:
            props["Serie"] = _rich_text(series_id)
        if data.spielkennung:
            props["Spielkennung"] = _rich_text(data.spielkennung)
        page = self._client.pages.create(
            parent={"database_id": self._settings.notion_buchungen_db_id},
            properties=props,
        )
        return self._page_to_booking(page)

    def get_upcoming_games(self, limit: int = 10) -> list[Booking]:
        """Gibt die nächsten bestätigten Spiele ab heute zurück."""
        pages = self._query_all(
            self._settings.notion_buchungen_db_id,
            filter={
                "and": [
                    {"property": "Typ", "select": {"equals": BookingType.SPIEL.value}},
                    {"property": "Status", "select": {"equals": BookingStatus.BESTAETIGT.value}},
                    {"property": "Datum", "date": {"on_or_after": date.today().isoformat()}},
                ]
            },
            sorts=[{"property": "Datum", "direction": "ascending"}],
        )
        return [self._page_to_booking(p) for p in pages[:limit]]

    # ------------------------------------------------------------------ ExternalEvents

    def _page_to_event(self, page: dict) -> ExternalEvent:
        props = page["properties"]
        raw_time = _get_rich_text(props, "Startzeit")
        parsed = _parse_time(raw_time) if raw_time else None
        return ExternalEvent(
            notion_id=page["id"],
            title=_get_title(props, "Name"),
            date=_get_date(props, "Datum") or date.today(),
            start_time=parsed or time(0, 0),
            location=_get_rich_text(props, "Ort") or None,
            description=_get_rich_text(props, "Beschreibung") or None,
            created_by_id=_get_rich_text(props, "Erstellt von ID"),
            created_by_name=_get_rich_text(props, "Erstellt von Name"),
        )

    def get_upcoming_events(self, limit: int = 10) -> list[ExternalEvent]:
        """Gibt die nächsten externen Termine ab heute zurück."""
        if not self._settings.notion_events_db_id:
            return []
        self._ensure_events_db_properties()
        pages = self._query_all(
            self._settings.notion_events_db_id,
            filter={"property": "Datum", "date": {"on_or_after": date.today().isoformat()}},
            sorts=[{"property": "Datum", "direction": "ascending"}],
        )
        return [self._page_to_event(p) for p in pages[:limit]]

    def get_all_events(self) -> list[ExternalEvent]:
        """Alle Events (vergangene + zukünftige) für die Verwaltungsseite, neueste zuerst."""
        if not self._settings.notion_events_db_id:
            return []
        self._ensure_events_db_properties()
        pages = self._query_all(
            self._settings.notion_events_db_id,
            sorts=[{"property": "Datum", "direction": "descending"}],
        )
        return [self._page_to_event(p) for p in pages]

    def create_event(
        self, data: ExternalEventCreate, user_id: str, user_name: str
    ) -> ExternalEvent:
        db_id = self._settings.notion_events_db_id
        if not db_id:
            raise ValueError("NOTION_EVENTS_DB_ID nicht konfiguriert")
        self._ensure_events_db_properties()
        props: dict[str, Any] = {
            "Name":               _title(data.title),
            "Datum":              _date_prop(data.date),
            "Startzeit":          _rich_text(data.start_time.strftime("%H:%M")),
            "Erstellt von ID":    _rich_text(user_id),
            "Erstellt von Name":  _rich_text(user_name),
        }
        if data.location:
            props["Ort"] = _rich_text(data.location)
        if data.description:
            props["Beschreibung"] = _rich_text(data.description)
        page = self._client.pages.create(
            parent={"database_id": db_id},
            properties=props,
        )
        return self._page_to_event(page)

    def delete_event(self, event_id: str) -> None:
        self._client.pages.update(page_id=event_id, archived=True)

    def get_bookings_by_spielkennung(self, kennungen: list[str]) -> dict[str, Booking]:
        """Gibt ein Dict {spielkennung: Booking} für alle bekannten Spielkennungen zurück."""
        if not kennungen:
            return {}
        result: dict[str, Booking] = {}
        for kennung in kennungen:
            pages = self._query_all(
                self._settings.notion_buchungen_db_id,
                filter={
                    "and": [
                        {"property": "Spielkennung", "rich_text": {"equals": kennung}},
                        {"property": "Status", "select": {"equals": BookingStatus.BESTAETIGT.value}},
                    ]
                },
            )
            if pages:
                booking = self._page_to_booking(pages[0])
                result[kennung] = booking
        return result

    def get_booking_by_id(self, booking_id: str) -> Optional[Booking]:
        try:
            page = self._client.pages.retrieve(page_id=booking_id)
            return self._page_to_booking(page)
        except Exception:
            return None

    def update_booking_status(self, booking_id: str, status: BookingStatus) -> Booking:
        page = self._update_page(booking_id, {"Status": _select(status.value)})
        return self._page_to_booking(page)

    def mark_series_exception(self, booking_id: str) -> Booking:
        page = self._update_page(
            booking_id,
            {
                "Status": _select(BookingStatus.STORNIERT.value),
                "Serienausnahme": _checkbox(True),
            },
        )
        return self._page_to_booking(page)

    # ------------------------------------------------------------------ series

    def _page_to_series(self, page: dict) -> Series:
        props = page["properties"]
        return Series(
            notion_id=page["id"],
            title=_get_title(props, "Titel"),
            field=FieldName(_get_select(props, "Platz")),
            start_time=_parse_time(_get_select(props, "Startzeit")),
            duration_min=int(_get_select(props, "Dauer") or 60),
            rhythm=SeriesRhythm(_get_select(props, "Rhythmus")),
            start_date=_get_date(props, "Startdatum"),
            end_date=_get_date(props, "Enddatum"),
            booked_by_id=_get_rich_text(props, "Gebucht von ID"),
            booked_by_name=_get_rich_text(props, "Gebucht von Name"),
            status=SeriesStatus(_get_select(props, "Status")),
            mannschaft=_get_rich_text(props, "Mannschaft") or None,
            trainer_id=_get_rich_text(props, "Trainer ID") or None,
            trainer_name=_get_rich_text(props, "Trainer Name") or None,
        )

    def create_series(
        self,
        data: SeriesCreate,
        booked_by_id: str,
        booked_by_name: str,
        trainer_name: str,
    ) -> Series:
        title = (
            f"Serie {data.mannschaft.value} {data.field.value} "
            f"{data.start_time.strftime('%H:%M')} "
            f"ab {data.start_date.isoformat()}"
        )
        page = self._client.pages.create(
            parent={"database_id": self._settings.notion_serien_db_id},
            properties={
                "Titel": _title(title),
                "Platz": _select(data.field.value),
                "Startzeit": _select(data.start_time.strftime("%H:%M")),
                "Dauer": _select(str(data.duration_min)),
                "Rhythmus": _select(data.rhythm.value),
                "Startdatum": _date_prop(data.start_date),
                "Enddatum": _date_prop(data.end_date),
                "Gebucht von ID": _rich_text(booked_by_id),
                "Gebucht von Name": _rich_text(booked_by_name),
                "Status": _select(SeriesStatus.AKTIV.value),
                "Mannschaft": _rich_text(data.mannschaft.value),
                "Trainer ID": _rich_text(data.trainer_id),
                "Trainer Name": _rich_text(trainer_name),
            },
        )
        return self._page_to_series(page)

    def get_all_series(self, only_active: bool = False) -> list[Series]:
        """Alle Serien, neueste zuerst. Optional nur aktive."""
        filter_: Optional[dict] = None
        if only_active:
            filter_ = {"property": "Status", "select": {"equals": SeriesStatus.AKTIV.value}}
        pages = self._query_all(
            self._settings.notion_serien_db_id,
            filter=filter_,
            sorts=[{"property": "Startdatum", "direction": "descending"}],
        )
        return [self._page_to_series(p) for p in pages]

    def update_series_status(self, series_id: str, status: SeriesStatus) -> Series:
        page = self._update_page(series_id, {"Status": _select(status.value)})
        return self._page_to_series(page)

    def get_series_by_id(self, series_id: str) -> Optional[Series]:
        try:
            page = self._client.pages.retrieve(page_id=series_id)
            return self._page_to_series(page)
        except Exception:
            return None

    # ------------------------------------------------------------------ blackout

    def _page_to_blackout(self, page: dict) -> Optional[BlackoutPeriod]:
        """Gibt None zurück wenn der Eintrag kein gültiges Datum hat."""
        props = page["properties"]
        start_date = _get_date(props, "Datum")
        if start_date is None:
            return None
        end_date = _get_date_end(props, "Datum") or start_date
        art = _get_select(props, "Art") or BlackoutType.GANZTAEGIG.value
        return BlackoutPeriod(
            notion_id=page["id"],
            title=_get_title(props, "Titel"),
            start_date=start_date,
            end_date=end_date,
            blackout_type=BlackoutType(art),
            start_time=_parse_time(_get_select(props, "Startzeit")),
            end_time=_parse_time(_get_select(props, "Endzeit")),
            reason=_get_rich_text(props, "Grund"),
            entered_by_id=_get_rich_text(props, "Eingetragen von ID"),
            entered_by_name=_get_rich_text(props, "Eingetragen von Name"),
        )

    def _blackouts_from_pages(self, pages: list[dict]) -> list[BlackoutPeriod]:
        return [bl for p in pages if (bl := self._page_to_blackout(p)) is not None]

    def get_blackouts_for_date(self, blackout_date: date) -> list[BlackoutPeriod]:
        # Fetch blackouts whose start_date <= blackout_date, then filter in Python for end_date >= blackout_date
        pages = self._query_all(
            self._settings.notion_sperrzeiten_db_id,
            filter={"property": "Datum", "date": {"on_or_before": blackout_date.isoformat()}},
        )
        return [bl for bl in self._blackouts_from_pages(pages) if bl.end_date >= blackout_date]

    def get_blackouts_for_week(self, year: int, week: int) -> list[BlackoutPeriod]:
        from datetime import timedelta
        monday = date.fromisocalendar(year, week, 1)
        sunday = monday + timedelta(days=6)
        # Fetch blackouts whose start_date <= sunday, then filter for end_date >= monday
        pages = self._query_all(
            self._settings.notion_sperrzeiten_db_id,
            filter={"property": "Datum", "date": {"on_or_before": sunday.isoformat()}},
        )
        return [bl for bl in self._blackouts_from_pages(pages) if bl.end_date >= monday]

    def get_all_blackouts(self) -> list[BlackoutPeriod]:
        """Alle Sperrzeiten, neueste zuerst."""
        pages = self._query_all(
            self._settings.notion_sperrzeiten_db_id,
            sorts=[{"property": "Datum", "direction": "descending"}],
        )
        return self._blackouts_from_pages(pages)

    def create_blackout(
        self,
        data: BlackoutCreate,
        entered_by_id: str,
        entered_by_name: str,
    ) -> BlackoutPeriod:
        if data.end_date > data.start_date:
            title = f"Sperrzeit Rasen {data.start_date.isoformat()} – {data.end_date.isoformat()}"
        else:
            title = f"Sperrzeit Rasen {data.start_date.isoformat()}"
        props: dict = {
            "Titel": _title(title),
            "Datum": _date_range_prop(data.start_date, data.end_date),
            "Art": _select(data.blackout_type.value),
            "Grund": _rich_text(data.reason),
            "Eingetragen von ID": _rich_text(entered_by_id),
            "Eingetragen von Name": _rich_text(entered_by_name),
        }
        if data.start_time:
            props["Startzeit"] = _select(data.start_time.strftime("%H:%M"))
        if data.end_time:
            props["Endzeit"] = _select(data.end_time.strftime("%H:%M"))
        page = self._client.pages.create(
            parent={"database_id": self._settings.notion_sperrzeiten_db_id},
            properties=props,
        )
        return self._page_to_blackout(page)

    def delete_blackout(self, blackout_id: str) -> None:
        self._client.pages.update(page_id=blackout_id, archived=True)

    # ------------------------------------------------------------------ aufgaben

    def _page_to_aufgabe(self, page: dict) -> Aufgabe:
        props = page["properties"]
        return Aufgabe(
            notion_id=page["id"],
            titel=_get_title(props, "Titel"),
            typ=AufgabeTyp(_get_select(props, "Typ")),
            status=AufgabeStatus(_get_select(props, "Status")),
            prioritaet=Prioritaet(_get_select(props, "Priorität")),
            erstellt_von_id=_get_rich_text(props, "Erstellt von ID"),
            erstellt_von_name=_get_rich_text(props, "Erstellt von Name"),
            erstellt_am=_get_date(props, "Erstellt am") or __import__("datetime").date.today(),
            faellig_am=_get_date(props, "Fällig am"),
            ort=_get_rich_text(props, "Ort") or None,
            beschreibung=_get_rich_text(props, "Beschreibung") or None,
        )

    def get_all_aufgaben(self, only_open: bool = False) -> list[Aufgabe]:
        filter_: Optional[dict] = None
        if only_open:
            filter_ = {"property": "Status", "select": {"does_not_equal": AufgabeStatus.ERLEDIGT.value}}
        pages = self._query_all(
            self._settings.notion_aufgaben_db_id,
            filter=filter_,
            sorts=[{"property": "Erstellt am", "direction": "descending"}],
        )
        return [self._page_to_aufgabe(p) for p in pages]

    def create_aufgabe(
        self,
        data: AufgabeCreate,
        created_by_id: str,
        created_by_name: str,
    ) -> Aufgabe:
        from datetime import date as _date
        props: dict = {
            "Titel": _title(data.titel),
            "Typ": _select(data.typ.value),
            "Status": _select(AufgabeStatus.OFFEN.value),
            "Priorität": _select(data.prioritaet.value),
            "Erstellt am": _date_prop(_date.today()),
            "Erstellt von ID": _rich_text(created_by_id),
            "Erstellt von Name": _rich_text(created_by_name),
        }
        if data.faellig_am:
            props["Fällig am"] = _date_prop(data.faellig_am)
        if data.ort:
            props["Ort"] = _rich_text(data.ort)
        if data.beschreibung:
            props["Beschreibung"] = _rich_text(data.beschreibung)
        page = self._client.pages.create(
            parent={"database_id": self._settings.notion_aufgaben_db_id},
            properties=props,
        )
        return self._page_to_aufgabe(page)

    def update_aufgabe_status(self, aufgabe_id: str, status: AufgabeStatus) -> Aufgabe:
        page = self._update_page(aufgabe_id, {"Status": _select(status.value)})
        return self._page_to_aufgabe(page)

    def delete_aufgabe(self, aufgabe_id: str) -> None:
        self._client.pages.update(page_id=aufgabe_id, archived=True)
