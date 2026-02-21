from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Notion
    notion_api_key: str
    notion_buchungen_db_id: str
    notion_serien_db_id: str
    notion_sperrzeiten_db_id: str
    notion_nutzer_db_id: str
    notion_aufgaben_db_id: str
    notion_events_db_id: Optional[str] = None  # Termine (extern, keine Platzbuchung)

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

    # Homepage
    booking_url: str = "http://46.62.212.248:1946"

    # Standort (Sonnenuntergang)
    location_lat: float = 52.264
    location_lon: float = 10.639
    location_name: str = "Cremlingen/Germany"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
