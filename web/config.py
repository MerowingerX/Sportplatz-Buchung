import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# ENV_FILE und CONFIG_DIR werden direkt aus der Systemumgebung gelesen –
# sie können nicht selbst in der .env-Datei stehen, da sie steuern, welche
# Datei geladen wird. Für den Demo-Server: ENV_FILE=.env.demo CONFIG_DIR=config/demo
_ENV_FILE = os.environ.get("ENV_FILE", ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8")

    # Notion
    notion_api_key: str
    notion_buchungen_db_id: str
    notion_serien_db_id: str
    notion_nutzer_db_id: str
    notion_aufgaben_db_id: str
    notion_events_db_id: Optional[str] = None        # Termine (extern, keine Platzbuchung)
    notion_mannschaften_db_id: Optional[str] = None  # Teams (Name, Trainer, FussballDeTeamId)

    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8

    # E-Mail
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    smtp_from: str
    admin_email: Optional[str] = None   # Crash-Mails; fällt auf smtp_from zurück wenn nicht gesetzt

    # fussball.de
    fussball_de_vereinsseite: Optional[str] = None  # z. B. https://www.fussball.de/verein/.../-/verein-id/00ES8GN…
    apifussball_token: Optional[str] = None          # api-fussball.de API-Token
    apifussball_club_id: Optional[str] = None        # Vereins-ID auf fussball.de (z. B. 00ES8GN76C000016VV0AG08LVUPGND5I)

    # Buchungssystem-URL (öffentlich erreichbar, wird in E-Mails verlinkt)
    booking_url: str = "http://localhost:1946"  # Fallback; wird durch BOOKING_URL in .env überschrieben

    # Standort (Sonnenuntergang) – in .env mit LOCATION_LAT/LON/NAME setzen
    location_lat: float = 52.5200   # Fallback: Berlin
    location_lon: float = 13.4050
    location_name: str = "Germany"

    # Notion-Property-Check beim Start überspringen (z. B. in Offline-Tests)
    skip_notion_migrate: bool = False


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
