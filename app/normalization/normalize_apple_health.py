from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BodyMetric, DailySummary, HeartRateSample, SleepSession, Workout
from app.normalization.normalize_steps import upsert_steps


def import_apple_health_payload(db: Session, user_id: int, payload: dict) -> dict[str, int]:
    counts = {"steps": 0, "sleep": 0, "heart_rate": 0, "workouts": 0, "calories": 0, "body_metrics": 0}
    for item in payload.get("steps", []):
        day = datetime.fromisoformat(item["date"]).date()
        upsert_steps(db, user_id, "Apple Health", day, int(item["count"]))
        db.flush()
        counts["steps"] += 1
    for item in payload.get("sleep", []):
        db.add(
            SleepSession(
                user_id=user_id,
                provider="Apple Health",
                start_time=_dt(item.get("start")),
                end_time=_dt(item.get("end")),
                sleep_hours=item.get("sleep_hours"),
                sleep_score=item.get("sleep_score"),
            )
        )
        counts["sleep"] += 1
    for item in payload.get("heart_rate", []):
        db.add(HeartRateSample(user_id=user_id, provider="Apple Health", sampled_at=_dt(item["sampled_at"]), bpm=item["bpm"], context=item.get("context")))
        counts["heart_rate"] += 1
    for item in payload.get("workouts", []):
        db.add(
            Workout(
                user_id=user_id,
                provider="Apple Health",
                activity_name=item.get("activity_name"),
                start_time=_dt(item.get("start")),
                end_time=_dt(item.get("end")),
                calories=item.get("calories"),
                average_heart_rate=item.get("average_heart_rate"),
            )
        )
        counts["workouts"] += 1
    for item in payload.get("calories", []):
        day = datetime.fromisoformat(item["date"]).date()
        summary = _summary_for_day(db, user_id, day)
        summary.calories = item.get("calories")
        db.add(summary)
        counts["calories"] += 1
    for item in payload.get("body_metrics", []):
        db.add(
            BodyMetric(
                user_id=user_id,
                provider="Apple Health",
                sampled_at=_dt(item["sampled_at"]),
                metric_type=item.get("type", "unknown"),
                value=item["value"],
                unit=item.get("unit", ""),
            )
        )
        counts["body_metrics"] += 1
    db.commit()
    return counts


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None) if value else None


def _summary_for_day(db: Session, user_id: int, day) -> DailySummary:
    summary = db.scalar(select(DailySummary).where(DailySummary.user_id == user_id, DailySummary.summary_date == day))
    if not summary:
        summary = DailySummary(user_id=user_id, summary_date=day, provider="Apple Health")
    return summary
