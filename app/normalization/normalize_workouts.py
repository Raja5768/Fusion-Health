from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailySummary, HeartRateSample, Workout
from app.normalization.utils import dump_raw, parse_day, parse_dt


def normalize_whoop_cycle(db: Session, user_id: int, payload: dict) -> DailySummary:
    score = payload.get("score") or {}
    day = parse_day(payload.get("start"))
    summary = db.scalar(select(DailySummary).where(DailySummary.user_id == user_id, DailySummary.summary_date == day))
    if not summary:
        summary = DailySummary(user_id=user_id, summary_date=day, provider="WHOOP")
    summary.strain = score.get("strain")
    summary.calories = _kj_to_calories(score.get("kilojoule"))
    summary.raw_json = dump_raw(payload)
    db.add(summary)
    if score.get("average_heart_rate") and payload.get("end"):
        db.add(HeartRateSample(user_id=user_id, provider="WHOOP", sampled_at=parse_dt(payload.get("end")), bpm=score["average_heart_rate"], context="cycle_average"))
    return summary


def normalize_whoop_workout(db: Session, user_id: int, payload: dict) -> Workout:
    score = payload.get("score") or {}
    workout_id = str(payload.get("id"))
    workout = db.scalar(select(Workout).where(Workout.user_id == user_id, Workout.provider_workout_id == workout_id))
    if not workout:
        workout = Workout(user_id=user_id, provider="WHOOP", provider_workout_id=workout_id)
    workout.activity_name = str(payload.get("sport_name") or payload.get("sport_id") or "Workout")
    workout.start_time = parse_dt(payload.get("start"))
    workout.end_time = parse_dt(payload.get("end"))
    workout.strain = score.get("strain")
    workout.average_heart_rate = score.get("average_heart_rate")
    workout.calories = _kj_to_calories(score.get("kilojoule"))
    workout.raw_json = dump_raw(payload)
    db.add(workout)
    if workout.average_heart_rate and workout.end_time:
        db.add(HeartRateSample(user_id=user_id, provider="WHOOP", sampled_at=workout.end_time, bpm=workout.average_heart_rate, context="workout_average"))
    return workout


def _kj_to_calories(value: int | float | None) -> float | None:
    return round(float(value) * 0.239006, 1) if value is not None else None
