from abc import ABC, abstractmethod
from datetime import date, time
from typing import Optional

from booking.models import (
    Aufgabe,
    AufgabeCreate,
    AufgabeStatus,
    BlackoutCreate,
    BlackoutPeriod,
    Booking,
    BookingCreate,
    BookingStatus,
    ExternalEvent,
    ExternalEventCreate,
    MannschaftConfig,
    Series,
    SeriesCreate,
    SeriesStatus,
    User,
    UserCreate,
    UserRole,
)


class AbstractRepository(ABC):

    # --- Nutzer ---

    @abstractmethod
    def get_user_by_name(self, name: str) -> Optional[User]: ...

    @abstractmethod
    def get_user_by_id(self, user_id: str) -> Optional[User]: ...

    @abstractmethod
    def create_user(self, user: UserCreate, password_hash: str) -> User: ...

    @abstractmethod
    def update_user_password(self, user_id: str, password_hash: str) -> User: ...

    @abstractmethod
    def reset_user_password(self, user_id: str, password_hash: str) -> User: ...

    @abstractmethod
    def update_user(
        self, user_id: str, role: str, email: str, mannschaft: Optional[str]
    ) -> User: ...

    @abstractmethod
    def delete_user(self, user_id: str) -> None: ...

    @abstractmethod
    def get_all_users(self) -> list[User]: ...

    @abstractmethod
    def get_trainers_for_mannschaft(self, mannschaft: str) -> list[User]: ...

    # --- Buchungen ---

    @abstractmethod
    def get_bookings_for_date(self, booking_date: date) -> list[Booking]: ...

    @abstractmethod
    def get_bookings_for_week(self, year: int, week: int) -> list[Booking]: ...

    @abstractmethod
    def get_bookings_for_series(
        self, series_id: str, only_future: bool = False
    ) -> list[Booking]: ...

    @abstractmethod
    def get_booking_by_id(self, booking_id: str) -> Optional[Booking]: ...

    @abstractmethod
    def get_upcoming_games(self, limit: int = 10) -> list[Booking]: ...

    @abstractmethod
    def get_bookings_by_spielkennung(
        self, kennungen: list[str]
    ) -> dict[str, Booking]: ...

    @abstractmethod
    def get_bookings_in_range(self, start: date, end: date) -> list[Booking]: ...

    @abstractmethod
    def get_all_bookings(self, from_date: Optional[date] = None) -> list[Booking]: ...

    @abstractmethod
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
    ) -> Booking: ...

    @abstractmethod
    def update_booking_status(
        self, booking_id: str, status: BookingStatus
    ) -> Booking: ...

    @abstractmethod
    def mark_series_exception(self, booking_id: str) -> Booking: ...

    @abstractmethod
    def enrich_booking(
        self,
        booking_id: str,
        mannschaft: Optional[str] = None,
        spielkennung: Optional[str] = None,
    ) -> None: ...

    # --- Serien ---

    @abstractmethod
    def get_all_series(self, only_active: bool = False) -> list[Series]: ...

    @abstractmethod
    def get_series_by_id(self, series_id: str) -> Optional[Series]: ...

    @abstractmethod
    def create_series(
        self,
        data: SeriesCreate,
        booked_by_id: str,
        booked_by_name: str,
        trainer_name: str,
    ) -> Series: ...

    @abstractmethod
    def update_series_status(
        self, series_id: str, status: SeriesStatus
    ) -> Series: ...

    # --- Sperrzeiten ---

    @abstractmethod
    def get_blackouts_for_date(
        self, blackout_date: date
    ) -> list[BlackoutPeriod]: ...

    @abstractmethod
    def get_blackouts_for_week(
        self, year: int, week: int
    ) -> list[BlackoutPeriod]: ...

    @abstractmethod
    def get_all_blackouts(self) -> list[BlackoutPeriod]: ...

    @abstractmethod
    def create_blackout(
        self,
        data: BlackoutCreate,
        entered_by_id: str,
        entered_by_name: str,
    ) -> BlackoutPeriod: ...

    @abstractmethod
    def delete_blackout(self, blackout_id: str) -> None: ...

    # --- Aufgaben ---

    @abstractmethod
    def get_all_aufgaben(self, only_open: bool = False) -> list[Aufgabe]: ...

    @abstractmethod
    def get_aufgabe_by_id(self, aufgabe_id: str) -> Optional[Aufgabe]: ...

    @abstractmethod
    def create_aufgabe(
        self,
        data: AufgabeCreate,
        created_by_id: str,
        created_by_name: str,
    ) -> Aufgabe: ...

    @abstractmethod
    def update_aufgabe_status(
        self, aufgabe_id: str, status: AufgabeStatus
    ) -> Aufgabe: ...

    @abstractmethod
    def delete_aufgabe(self, aufgabe_id: str) -> None: ...

    # --- Events ---

    @abstractmethod
    def get_upcoming_events(self, limit: int = 10) -> list[ExternalEvent]: ...

    @abstractmethod
    def get_all_events(self) -> list[ExternalEvent]: ...

    @abstractmethod
    def get_event_by_id(self, event_id: str) -> Optional[ExternalEvent]: ...

    @abstractmethod
    def create_event(
        self, data: ExternalEventCreate, user_id: str, user_name: str
    ) -> ExternalEvent: ...

    @abstractmethod
    def delete_event(self, event_id: str) -> None: ...

    # --- Mannschaften ---

    @abstractmethod
    def get_all_mannschaften(
        self, only_active: bool = False
    ) -> list[MannschaftConfig]: ...

    @abstractmethod
    def get_mannschaft_by_id(self, mannschaft_id: str) -> Optional[MannschaftConfig]: ...

    @abstractmethod
    def create_mannschaft(
        self,
        name: str,
        trainer_id: Optional[str],
        trainer_name: Optional[str],
        fussball_de_team_id: Optional[str],
        cc_emails: list[str],
        aktiv: bool = True,
        shortname: Optional[str] = None,
    ) -> MannschaftConfig: ...

    @abstractmethod
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
    ) -> MannschaftConfig: ...

    @abstractmethod
    def delete_mannschaft(self, mannschaft_id: str) -> None: ...
