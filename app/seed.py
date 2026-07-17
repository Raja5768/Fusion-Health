from sqlalchemy import select

from app.database import SessionLocal
from app.models import Provider


def seed_providers() -> None:
    providers = [
        ("whoop", "WHOOP", True),
        ("apple_health", "Apple Health", False),
        ("fitbit", "Fitbit", False),
        ("garmin", "Garmin", False),
        ("oura", "Oura", False),
        ("strava", "Strava", False),
        ("google_health_connect", "Google Health Connect", False),
    ]
    with SessionLocal() as db:
        for name, display_name, enabled in providers:
            if not db.scalar(select(Provider).where(Provider.name == name)):
                db.add(Provider(name=name, display_name=display_name, enabled=enabled))
        db.commit()
