import os
import secrets
from datetime import date, datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import JSON, Date, DateTime, Float, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


def database_url() -> str:
    value = os.getenv("DATABASE_URL", "sqlite:///./fusion_health.db")
    return value.replace("postgres://", "postgresql://", 1)


engine = create_engine(database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class HealthImport(Base):
    __tablename__ = "health_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(80), default="Apple Health")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DailyActivity(Base):
    __tablename__ = "daily_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    steps: Mapped[int] = mapped_column(Integer, default=0)
    calories: Mapped[float] = mapped_column(Float, default=0)
    provider: Mapped[str] = mapped_column(String(80), default="Apple Health")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HealthPayload(BaseModel):
    steps: list[dict[str, Any]] = Field(default_factory=list)
    sleep: list[dict[str, Any]] = Field(default_factory=list)
    heart_rate: list[dict[str, Any]] = Field(default_factory=list)
    workouts: list[dict[str, Any]] = Field(default_factory=list)
    calories: list[dict[str, Any]] = Field(default_factory=list)
    body_metrics: list[dict[str, Any]] = Field(default_factory=list)


app = FastAPI(title="Fusion Health API", version="1.0.0")


@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(engine)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("FUSION_HEALTH_API_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="Server API key is not configured.")
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="The API key is invalid.")


def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/import/apple-health", dependencies=[Depends(require_api_key)])
def import_apple_health(
    payload: HealthPayload,
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    imported_at = datetime.now(timezone.utc)
    values = payload.model_dump()
    session.add(HealthImport(payload=values, imported_at=imported_at))
    daily_values: dict[str, dict[str, Any]] = {}
    for item in values["steps"]:
        day = item.get("date")
        if day:
            daily_values.setdefault(day, {"steps": 0, "calories": 0.0})["steps"] += int(item.get("count", 0))
    for item in values["calories"]:
        day = item.get("date")
        if day:
            daily_values.setdefault(day, {"steps": 0, "calories": 0.0})["calories"] += float(item.get("calories", 0))

    for day, activity in daily_values.items():
        try:
            activity_date = date.fromisoformat(day)
        except ValueError:
            continue
        record = session.scalar(select(DailyActivity).where(DailyActivity.activity_date == activity_date))
        if record is None:
            record = DailyActivity(activity_date=activity_date, updated_at=imported_at)
            session.add(record)
        record.steps = int(activity["steps"])
        record.calories = round(float(activity["calories"]), 1)
        record.updated_at = imported_at
    session.commit()

    return {
        "provider": "Apple Health",
        "imported": {name: len(records) for name, records in values.items()},
        "imported_at": imported_at.isoformat().replace("+00:00", "Z"),
    }


@app.get("/api/v1/daily", dependencies=[Depends(require_api_key)])
def daily_activity_history(
    limit: int = 30,
    session: Session = Depends(db_session),
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 365))
    records = session.scalars(
        select(DailyActivity).order_by(DailyActivity.activity_date.desc()).limit(safe_limit)
    ).all()
    return [daily_activity_response(record) for record in records]


@app.get("/api/v1/daily/{activity_date}", dependencies=[Depends(require_api_key)])
def daily_activity_by_date(
    activity_date: date,
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    record = session.scalar(select(DailyActivity).where(DailyActivity.activity_date == activity_date))
    if record is None:
        raise HTTPException(status_code=404, detail="No activity was found for that date.")
    return daily_activity_response(record)


def daily_activity_response(record: DailyActivity) -> dict[str, Any]:
    return {
        "date": record.activity_date,
        "steps": record.steps,
        "calories": round(record.calories, 1),
        "provider": record.provider,
        "updated_at": record.updated_at,
    }


@app.get("/api/v1/export/latest", dependencies=[Depends(require_api_key)])
def export_latest(session: Session = Depends(db_session)) -> dict[str, Any]:
    record = session.scalar(select(HealthImport).order_by(HealthImport.imported_at.desc()).limit(1))
    if not record:
        raise HTTPException(status_code=404, detail="No health data has been imported.")
    return {
        "provider": record.provider,
        "imported_at": record.imported_at,
        **record.payload,
    }


@app.get("/api/v1/summary/today", dependencies=[Depends(require_api_key)])
def summary_today(session: Session = Depends(db_session)) -> dict[str, Any]:
    record = session.scalar(select(HealthImport).order_by(HealthImport.imported_at.desc()).limit(1))
    if not record:
        raise HTTPException(status_code=404, detail="No health data has been imported.")

    today = date.today().isoformat()
    payload = record.payload
    steps = sum(int(item.get("count", 0)) for item in payload.get("steps", []) if item.get("date") == today)
    calories = sum(float(item.get("calories", 0)) for item in payload.get("calories", []) if item.get("date") == today)
    heart_rates = [float(item["bpm"]) for item in payload.get("heart_rate", []) if item.get("bpm") is not None]

    return {
        "summary_date": today,
        "steps": steps,
        "calories": round(calories, 1),
        "average_heart_rate": round(sum(heart_rates) / len(heart_rates), 1) if heart_rates else None,
        "workouts": len(payload.get("workouts", [])),
        "provider": record.provider,
        "imported_at": record.imported_at,
    }
